"""Central metadata-only API and optional dashboard static server."""

import argparse
import asyncio
import base64
import binascii
from contextlib import asynccontextmanager, suppress
import json
import os
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
import uvicorn

from backend.saas.auth import Authenticator
from backend.saas import benchmark
from backend.saas.health import HealthMonitor
from backend.saas.incidents import IncidentEngine
from backend.saas.remediation import Remediation, public_action
from backend.shared.remediation import CommandResult
from backend.saas.storage import PayloadConflict, Storage
from backend.shared.config import Credential, ServerSettings, read_settings
from backend.shared.models import (
    CollectorHeartbeat, Identifier, IngestReceipt, MetadataPayload, PayloadDetail, UuidString,
    parse_utc, utc_now, utc_text,
)


def unique_keys(pairs):
    result = dict(pairs)
    if len(result) != len(pairs):
        raise ValueError("Duplicate JSON key")
    return result


class BoundedJSONRoute(APIRoute):
    """Bound the collector body before FastAPI parses it."""

    def get_route_handler(self):
        handle = super().get_route_handler()

        async def bounded(request: Request):
            if request.method != "POST":
                return await handle(request)
            data = bytearray()
            async for chunk in request.stream():
                if len(data) + len(chunk) > 16_384:
                    raise HTTPException(413, "Metadata body too large")
                data.extend(chunk)
            try:
                if data:
                    json.loads(data.decode("utf-8"), object_pairs_hook=unique_keys)
            except (ValueError, RecursionError):
                raise HTTPException(422, "Invalid metadata schema") from None

            sent = False

            async def receive():
                nonlocal sent
                if sent:
                    return await request.receive()
                sent = True
                return {"type": "http.request", "body": bytes(data), "more_body": False}

            return await handle(Request(request.scope, receive=receive))

        return bounded


def decode_cursor(cursor: str | None) -> tuple[str, str]:
    if cursor is None:
        return "", ""
    try:
        result = json.loads(base64.urlsafe_b64decode(cursor))
        if not isinstance(result, list) or len(result) != 2 or not all(isinstance(v, str) for v in result):
            raise ValueError()
        if utc_text(parse_utc(result[0])) != result[0] or len(result[1]) != 36:
            raise ValueError()
        return result[0], result[1]
    except (ValueError, binascii.Error):
        raise HTTPException(400, "Invalid cursor") from None


def create_app(settings: ServerSettings, db_path: Path, dashboard: Path | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with Storage.open(db_path) as storage:
            app.state.storage = storage
            app.state.monitor = HealthMonitor(storage, settings.health, sources_by_tenant)
            storage.on_change = app.state.monitor.refresh_locked
            app.state.incidents = IncidentEngine(storage, settings)
            storage.analyze = app.state.incidents.analyze_locked
            app.state.remediation = Remediation(storage, settings)
            watchdog = asyncio.create_task(app.state.monitor.watch())
            try:
                yield
            finally:
                watchdog.cancel()
                with suppress(asyncio.CancelledError):
                    await watchdog

    app = FastAPI(
        title="Cicada Metadata API", version="0.1.0", lifespan=lifespan,
        openapi_url=None, docs_url=None, redoc_url=None,
    )
    app.router.route_class = BoundedJSONRoute
    auth = Authenticator(settings)
    sources_by_tenant: dict[str, set[str]] = {}
    for credential in settings.credentials:
        sources_by_tenant.setdefault(credential.tenant_id, set()).update(credential.source_ids)
    if settings.dev_origin:
        app.add_middleware(
            CORSMiddleware, allow_origins=[settings.dev_origin], allow_methods=["GET", "POST"],
            allow_headers=["Authorization", "Content-Type", "X-Tenant-ID"],
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, _error: RequestValidationError):
        # Never echo rejected keys, values, or unapproved request bytes.
        return JSONResponse({"detail": "Invalid request schema"}, status_code=422)

    def collector(request: Request) -> Credential:
        return auth.require(request, "collector")

    def operator(request: Request) -> Credential:
        return auth.require(request, "operator")

    def store(request: Request) -> Storage:
        return request.app.state.storage

    def require_collector_identity(wire: MetadataPayload | CollectorHeartbeat, credential: Credential):
        if (wire.tenant_id, wire.collector_id, wire.region) != (
            credential.tenant_id, credential.collector_id, credential.region
        ):
            raise HTTPException(403, "Collector scope mismatch")

    @app.get("/healthz")
    async def health():
        return {"status": "ok"}

    @app.post("/api/v1/ingest/{region}", response_model=IngestReceipt)
    async def ingest(
        region: str, payload: MetadataPayload, request: Request,
        credential: Credential = Depends(collector), storage: Storage = Depends(store),
    ):
        require_collector_identity(payload, credential)
        if region != credential.region or payload.source_id not in credential.source_ids:
            raise HTTPException(403, "Region or source scope mismatch")
        if payload.simulation and payload.source_id not in credential.demo_source_ids:
            raise HTTPException(403, "Source is not configured for simulation")
        if (parse_utc(payload.event_time_utc) - utc_now()).total_seconds() > 5:
            raise HTTPException(422, "Event timestamp is in the future")
        try:
            return await storage.ingest(payload, await request.body())
        except PayloadConflict:
            raise HTTPException(409, "Payload ID already has different bytes") from None

    @app.post("/api/v1/heartbeats")
    async def heartbeat(
        beat: CollectorHeartbeat,
        credential: Credential = Depends(collector), storage: Storage = Depends(store),
    ):
        require_collector_identity(beat, credential)
        if not -5 <= (utc_now() - parse_utc(beat.generated_at_utc)).total_seconds() <= 15:
            raise HTTPException(422, "Heartbeat is outside the freshness window")
        refreshed = await storage.heartbeat(beat)
        return {"heartbeat_uuid": beat.heartbeat_uuid, "refreshed": refreshed}

    @app.get("/api/v1/payloads/{payload_uuid}", response_model=PayloadDetail)
    async def payload_detail(
        payload_uuid: UuidString, credential: Credential = Depends(operator), storage: Storage = Depends(store),
    ):
        result = await storage.payload(credential.tenant_id, payload_uuid)
        if result is None:
            raise HTTPException(404, "Payload not found")
        return result

    @app.get("/api/v1/sources/{source_id}/metrics")
    async def source_metrics(
        source_id: str, credential: Credential = Depends(operator), storage: Storage = Depends(store),
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
        cursor: Annotated[str | None, Query(max_length=256)] = None,
        recent: bool = False,
    ):
        if source_id not in sources_by_tenant[credential.tenant_id]:
            raise HTTPException(404, "Source not found")
        if recent:
            if cursor is not None:
                raise HTTPException(400, "Recent snapshots do not accept a cursor")
            rows = await storage.recent_metrics(credential.tenant_id, source_id, limit)
            return {"items": [storage.detail(row) for row in rows], "next_cursor": None}
        rows = await storage.metrics(credential.tenant_id, source_id, decode_cursor(cursor), limit + 1)
        items = rows[:limit]
        next_cursor = None
        if len(rows) > limit:
            next_cursor = base64.urlsafe_b64encode(
                json.dumps([items[-1]["event_time"], items[-1]["payload_uuid"]]).encode()
            ).decode()
        return {"items": [storage.detail(row) for row in items], "next_cursor": next_cursor}

    @app.get("/api/v1/fleet")
    async def fleet(request: Request, credential: Credential = Depends(operator)):
        return await request.app.state.monitor.snapshot(credential.tenant_id)

    @app.get("/api/v1/transitions")
    async def transitions(
        request: Request, credential: Credential = Depends(operator),
        cursor: Annotated[int, Query(ge=1, le=2**63 - 1)] = 2**63 - 1,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ):
        return await request.app.state.monitor.transitions(credential.tenant_id, cursor, limit)

    @app.post("/api/v1/benchmarks/render")
    async def record_render(
        receipt: benchmark.RenderReceipt, credential: Credential = Depends(operator),
        storage: Storage = Depends(store),
    ):
        result = await benchmark.record(storage, credential.tenant_id, receipt)
        if result is None:
            raise HTTPException(404, "Payload not found")
        return {"accepted": True, "first_recorded": result}

    @app.get("/api/v1/incidents")
    async def incidents(
        request: Request, credential: Credential = Depends(operator),
        cursor: Annotated[int, Query(ge=1, le=2**63 - 1)] = 2**63 - 1,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ):
        return await request.app.state.incidents.list(credential.tenant_id, cursor, limit)

    @app.get("/api/v1/incidents/{incident_id}")
    async def incident_detail(incident_id: UuidString, request: Request, credential: Credential = Depends(operator)):
        detail = await request.app.state.incidents.detail(credential.tenant_id, incident_id)
        if detail is None:
            raise HTTPException(404, "Incident not found")
        remediation = request.app.state.remediation
        async with remediation.storage.lock:
            proposal = await remediation.by_incident(credential.tenant_id, incident_id)
            eligible = proposal is None and await remediation.target(credential.tenant_id, incident_id) is not None
        return {**detail, "proposal": public_action(proposal) if proposal else None,
                "proposal_status": proposal["status"] if proposal else "none", "remediation_eligible": eligible}

    async def require_empty_action_request(request: Request):
        if await request.body():
            raise HTTPException(422, "The simulation accepts no action parameters")

    @app.post("/api/v1/incidents/{incident_id}/proposal", dependencies=[Depends(require_empty_action_request)])
    async def propose(incident_id: UuidString, request: Request, credential: Credential = Depends(operator)):
        return await request.app.state.remediation.propose(credential, incident_id)

    @app.post("/api/v1/remediation/{action_id}/approve", dependencies=[Depends(require_empty_action_request)])
    async def approve(action_id: UuidString, request: Request, credential: Credential = Depends(operator)):
        return await request.app.state.remediation.approve(credential, action_id)

    @app.post("/api/v1/remediation/{action_id}/rollback", dependencies=[Depends(require_empty_action_request)])
    async def rollback(action_id: UuidString, request: Request, credential: Credential = Depends(operator)):
        return await request.app.state.remediation.rollback(credential, action_id)

    @app.get("/api/v1/remediation/audit")
    async def remediation_audit(
        request: Request, credential: Credential = Depends(operator),
        cursor: Annotated[int, Query(ge=1, le=2**63 - 1)] = 2**63 - 1,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ):
        return await request.app.state.remediation.audit_page(credential.tenant_id, cursor, limit)

    @app.get("/api/v1/collector/commands")
    async def collector_commands(request: Request, credential: Credential = Depends(collector)):
        return await request.app.state.remediation.commands(credential)

    @app.post("/api/v1/collector/commands/{command_id}/result")
    async def collector_result(
        command_id: UuidString, result: CommandResult, request: Request, credential: Credential = Depends(collector),
    ):
        return await request.app.state.remediation.complete(credential, command_id, result)

    @app.get("/api/v1/benchmarks")
    async def benchmarks(
        credential: Credential = Depends(operator), storage: Storage = Depends(store),
        run_id: Identifier = "default-run", session_id: Identifier | None = None,
    ):
        return await benchmark.summary(storage, credential.tenant_id, run_id, session_id)


    if dashboard is not None:
        index = dashboard / "index.html"
        if not index.is_file():
            raise ValueError("Dashboard build index.html does not exist")
        app.mount("/assets", StaticFiles(directory=dashboard / "assets"), name="dashboard-assets")

        @app.get("/", include_in_schema=False)
        async def dashboard_index():
            return FileResponse(index)

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", type=Path, default=Path(os.getenv("CICADA_RUNTIME", ".cicada/dev")))
    parser.add_argument("--port", type=int, default=8443)
    parser.add_argument("--dashboard", type=Path, default=os.getenv("CICADA_DASHBOARD_DIR"))
    args = parser.parse_args()
    app = create_app(read_settings(args.runtime / "saas.json", ServerSettings),
                     args.runtime / "saas.sqlite", args.dashboard)
    uvicorn.run(
        app, host="127.0.0.1", port=args.port, ssl_keyfile=str(args.runtime / "server.key"),
        ssl_certfile=str(args.runtime / "server.pem"), proxy_headers=False,
    )


if __name__ == "__main__":
    main()
