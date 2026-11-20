"""Retry approved bodies until a matching committed receipt arrives."""

import asyncio
import logging
from random import uniform

import httpx
from pydantic import ValidationError

from backend.collector.buffer_queue import Outbox
from backend.collector.inspector import AuditPreview
from backend.collector.transport import DELIVERY_ERRORS, Transport
from backend.shared.models import MetadataPayload, canonical_bytes

LOG = logging.getLogger("heimdal.collector")
QUARANTINE_CODES = {400: "invalid_body", 409: "uuid_conflict", 413: "body_too_large", 422: "invalid_body"}


class Drainer:
    def __init__(self, outbox: Outbox, transport: Transport, audit: AuditPreview):
        self.outbox = outbox
        self.transport = transport
        self.audit = audit
        self.receipts = {"accepted": 0, "duplicate": 0}

    async def run(self):
        while True:
            if not await self.deliver_next():
                await asyncio.sleep(0.25)

    async def deliver_next(self) -> bool:
        row = await self.outbox.next_ready()
        if row is None:
            return False

        row_id, body, uuid = row["id"], row["body"], row["payload_uuid"]
        try:
            payload = MetadataPayload.model_validate_json(body)
        except ValidationError:
            await self.outbox.quarantine(row_id, "invalid_local_body")
            return True
        if payload.payload_uuid != uuid or canonical_bytes(payload) != body:
            await self.outbox.quarantine(row_id, "invalid_local_body")
            return True

        record = self.audit.by_id(uuid, approved_body=body.decode())
        if record is not None:
            record["state"] = "sending"
        try:
            receipt = await self.transport.send(payload, body)
        except DELIVERY_ERRORS as error:
            status = error.response.status_code if isinstance(error, httpx.HTTPStatusError) else None
            reason = QUARANTINE_CODES.get(status)
            if reason:
                await self.outbox.quarantine(row_id, reason)
                state = "quarantined"
            else:
                delay = uniform(0.5, 1.0) * min(8, 2 ** min(row["attempts"], 3))
                await self.outbox.retry(row_id, delay)
                state = "retrying"
            if record is not None:
                record["state"] = state
            LOG.warning("Payload %s %s (%s)", uuid, state, reason or type(error).__name__)
        else:
            await self.outbox.acknowledge(row_id)
            self.receipts[receipt.status] += 1
            if record is not None:
                record["receipt"] = receipt.model_dump(mode="json")
                record["state"] = "acknowledged"
        return True
