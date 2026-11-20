"""Loopback-only inspection for real local preview and receipt data."""

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from hashlib import sha256
from hmac import compare_digest
from pathlib import Path
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, Response
from uuid import UUID

from backend.collector.demo_source import RawEvent
from backend.collector.scenario_runner import ScenarioBusy, ScenarioRunner
from backend.collector.scrubber import scrub_preview
from backend.collector.transport import DELIVERY_ERRORS
from backend.shared.config import CollectorSettings
from backend.shared.models import MetadataPayload
from backend.shared.scenarios import ScenarioNumber

STATIC = Path(__file__).with_name("static")

JS = """document.querySelector('form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const set = (id, text) => { document.getElementById(id).textContent = text; };
  for (const id of ['status', 'identity', 'raw', 'approved', 'receipt']) set(id, '');
  try {
    const token = document.getElementById('token').value;
    const uuid = document.getElementById('lookup').value.trim();
    const path = uuid ? '/api/local/audit?payload_uuid=' + encodeURIComponent(uuid) : '/api/local/audit';
    const response = await fetch(path, {
      headers: { Authorization: 'Bearer ' + token }, cache: 'no-store'
    });
    if (!response.ok) throw new Error('Inspection unavailable (' + response.status + ').');
    const {items} = await response.json();
    if (!items.length) { set('status', 'No retained records.'); return; }
    const {raw_preview, approved_body, ...receipt} = items[0];
    set('identity', receipt.payload_uuid + '\\n' + receipt.body_sha256);
    set('raw', raw_preview || '(No raw text)');
    set('approved', approved_body);
    set('receipt', JSON.stringify(receipt, null, 2));
  } catch (error) {
    set('status', error.message);
  }
});"""


class AuditPreview:
    def __init__(self, max_records=500, ttl_seconds=900):
        self.records = deque(maxlen=max_records)
        self.ttl = ttl_seconds

    def purge(self):
        deadline = monotonic() - self.ttl
        while self.records and self.records[0][0] <= deadline:
            self.records.popleft()

    def add(self, event: RawEvent, payload: MetadataPayload, approved: bytes) -> dict:
        self.purge()
        record = {
            "payload_uuid": payload.payload_uuid,
            "policy_version": payload.policy_version,
            "raw_preview": scrub_preview(event.raw_text[:8192]) if isinstance(event.raw_text, str) else None,
            "approved_body": approved.decode(),
            "body_sha256": sha256(approved).hexdigest(),
            "state": "constructed",
            "receipt": None,
        }
        self.records.append((monotonic(), record))
        return record

    def latest(self, limit: int = 20):
        self.purge()
        return [record for _, record in reversed(self.records)][:limit]

    def by_id(self, payload_uuid: str, approved_body: str | None = None):
        self.purge()
        return next((
            record for _, record in reversed(self.records)
            if record["payload_uuid"] == payload_uuid
            and (approved_body is None or record["approved_body"] == approved_body)
        ), None)


def create_inspector(
    settings: CollectorSettings, audit: AuditPreview, queue_status: Callable[[], Awaitable[dict]],
    scenarios: ScenarioRunner | None = None,
) -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app):
        async def purge_periodically():
            while True:
                audit.purge()
                await asyncio.sleep(5)

        task = asyncio.create_task(purge_periodically())
        try:
            yield
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    app = FastAPI(openapi_url=None, docs_url=None, redoc_url=None, lifespan=lifespan)
    hosts = {f"localhost:{settings.local_port}", f"127.0.0.1:{settings.local_port}"}
    expected = f"Bearer {settings.local_token.get_secret_value()}".encode()

    @app.middleware("http")
    async def restrict_request(request: Request, call_next):
        host = request.headers.getlist("host")
        origin = request.headers.getlist("origin")
        if len(host) != 1 or host[0] not in hosts or origin not in ([], [f"http://{host[0]}"]):
            return Response(status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = (
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'none'"
        )
        return response

    def check_token(request: Request):
        header = request.headers.getlist("authorization")
        if len(header) != 1 or not compare_digest(header[0].encode(), expected):
            raise HTTPException(401, "Local session required")

    @app.get("/audit")
    async def page():
        return FileResponse(STATIC / "proof.html", media_type="text/html")

    @app.get("/theme.js")
    async def theme_script():
        return FileResponse(STATIC / "theme.js", media_type="text/javascript")

    @app.get("/theme.css")
    async def theme_styles():
        return FileResponse(STATIC / "theme.css", media_type="text/css")

    @app.get("/collector.css")
    async def stylesheet():
        return FileResponse(STATIC / "collector.css", media_type="text/css")

    @app.get("/audit.js")
    async def script():
        return Response(JS, media_type="text/javascript")

    @app.get("/api/local/audit")
    async def records(request: Request, payload_uuid: str | None = None):
        check_token(request)
        if payload_uuid is not None:
            try:
                key = str(UUID(payload_uuid))
            except ValueError:
                raise HTTPException(400, "Invalid payload UUID") from None
            result = audit.by_id(key)
            if result is None:
                raise HTTPException(404, "No retained record for this UUID")
            return {"items": [result]}
        return {"items": audit.latest()}

    @app.get("/api/local/status")
    async def status(request: Request):
        check_token(request)
        return {"retained_previews": len(audit.latest(500)), **await queue_status()}

    if scenarios is not None:
        @app.get("/scenarios")
        async def scenario_page():
            return FileResponse(STATIC / "scenarios.html", media_type="text/html")

        @app.get("/scenarios.js")
        async def scenario_script():
            return Response(SCENARIO_JS, media_type="text/javascript")

        @app.get("/api/local/scenarios")
        async def scenario_status(request: Request):
            check_token(request)
            return {"result": scenarios.current, "publishing": bool(scenarios.pending)}

        @app.post("/api/local/scenarios/{number}", status_code=202)
        async def start_scenario(number: ScenarioNumber, request: Request):
            check_token(request)
            try:
                return await scenarios.start(number)
            except ScenarioBusy as error:
                raise HTTPException(409, str(error)) from None

        @app.post("/api/local/reset")
        async def reset_scenario(request: Request):
            check_token(request)
            try:
                await scenarios.reset()
            except ScenarioBusy as error:
                raise HTTPException(409, str(error)) from None
            except DELIVERY_ERRORS:
                raise HTTPException(503, "Cannot verify pending actions") from None
            return {"reset": True}

    return app


SCENARIO_JS = """const token = document.getElementById('token');
const status = document.getElementById('status');
const result = document.getElementById('result');
let timer;
async function request(path, method = 'GET') {
  const response = await fetch(path, { method, headers: { Authorization: 'Bearer ' + token.value } });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Request failed');
  return data;
}
async function refresh() {
  try {
    const state = await request('/api/local/scenarios');
    result.textContent = state.result ? JSON.stringify(state.result, null, 2) : '';
    status.textContent = state.publishing && state.result?.status !== 'running' ? 'Publishing evidence…' : '';
  } catch (error) { status.textContent = error.message; }
}
async function act(path) {
  window.clearInterval(timer);
  try {
    await request(path, 'POST');
    await refresh();
  } catch (error) { status.textContent = error.message; }
  timer = window.setInterval(refresh, 2000);
}
document.querySelectorAll('[data-run]').forEach(button => {
  button.addEventListener('click', () => act('/api/local/scenarios/' + button.dataset.run));
});
document.getElementById('reset').addEventListener('click', () => act('/api/local/reset'));
token.addEventListener('change', refresh);
"""
