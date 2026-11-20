"""Verified HTTPS transport for approved bytes only."""

import hashlib
from pathlib import Path
import ssl
from urllib.parse import urlsplit

import httpx

from backend.shared.config import CollectorSettings
from backend.shared.models import CollectorHeartbeat, IngestReceipt, MetadataPayload, canonical_bytes


class ReceiptMismatch(Exception):
    pass


class Transport:
    def __init__(self, settings: CollectorSettings, ca_file: Path):
        endpoint = urlsplit(settings.saas_url)
        if (endpoint.scheme != "https" or not endpoint.hostname or endpoint.username is not None
                or endpoint.query or endpoint.fragment or endpoint.path not in ("", "/")):
            raise ValueError("SaaS endpoint must be an HTTPS origin")
        self.region = settings.region
        self.client = httpx.AsyncClient(
            base_url=settings.saas_url, verify=ssl.create_default_context(cafile=str(ca_file)),
            trust_env=False, follow_redirects=False, timeout=5,
            headers={
                "Authorization": f"Bearer {settings.token.get_secret_value()}",
                "X-Tenant-ID": settings.tenant_id, "Content-Type": "application/json",
            },
        )

    async def __aenter__(self):
        await self.client.__aenter__()
        return self

    async def __aexit__(self, *exc):
        await self.client.__aexit__(*exc)

    async def send(self, payload: MetadataPayload, approved: bytes) -> IngestReceipt:
        response = await self.client.post(f"/api/v1/ingest/{self.region}", content=approved)
        response.raise_for_status()
        receipt = IngestReceipt.model_validate_json(response.content)
        if receipt.payload_uuid != payload.payload_uuid or receipt.body_sha256 != hashlib.sha256(approved).hexdigest():
            raise ReceiptMismatch("Receipt did not match the approved bytes")
        return receipt

    async def heartbeat(self, beat: CollectorHeartbeat):
        response = await self.client.post("/api/v1/heartbeats", content=canonical_bytes(beat))
        response.raise_for_status()
