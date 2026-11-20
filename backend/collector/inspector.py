"""Loopback-only inspection for real local preview and receipt data."""

import asyncio
from collections import deque
from contextlib import asynccontextmanager
from hashlib import sha256
from hmac import compare_digest
from time import monotonic

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response

from backend.collector.demo_source import RawEvent
from backend.shared.config import CollectorSettings
from backend.shared.models import MetadataPayload

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>Cicada local egress proof</title><script src="/audit.js" defer></script></head><body>
<h1>Local egress proof</h1>
<p>Use the collector's local session token to inspect the latest record.</p>
<form><label>Local session token <input type="password" required autocomplete="off"></label>
<button>Fetch latest record</button></form><p id="status" role="status"></p>
<h2>Local input preview</h2><pre id="raw"></pre>
<h2>Exact approved outbound bytes</h2><pre id="approved"></pre>
<h2>Delivery and receipt</h2><pre id="receipt"></pre></body></html>"""

JS = """document.querySelector('form').addEventListener('submit', async (event) => {
  event.preventDefault();
  const set = (id, text) => { document.getElementById(id).textContent = text; };
  for (const id of ['status', 'raw', 'approved', 'receipt']) set(id, '');
  try {
    const token = document.querySelector('input').value;
    const response = await fetch('/api/local/audit', {
      headers: { Authorization: 'Bearer ' + token }, cache: 'no-store'
    });
    if (!response.ok) throw new Error('Inspection unavailable (' + response.status + ').');
    const {items} = await response.json();
    if (!items.length) { set('status', 'No retained records.'); return; }
    const {raw_preview, approved_body, ...receipt} = items[0];
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
            "raw_preview": event.raw_text[:8192] if isinstance(event.raw_text, str) else None,
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


def create_inspector(settings: CollectorSettings, audit: AuditPreview) -> FastAPI:
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
            "default-src 'none'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'none'"
        )
        return response

    def check_token(request: Request):
        header = request.headers.getlist("authorization")
        if len(header) != 1 or not compare_digest(header[0].encode(), expected):
            raise HTTPException(401, "Local session required")

    @app.get("/audit")
    async def page():
        return HTMLResponse(PAGE)

    @app.get("/audit.js")
    async def script():
        return Response(JS, media_type="text/javascript")

    @app.get("/api/local/audit")
    async def records(request: Request):
        check_token(request)
        return {"items": audit.latest()}

    @app.get("/api/local/status")
    async def status(request: Request):
        check_token(request)
        return {"retained_previews": len(audit.latest(500)), "buffering": "not_enabled"}

    return app
