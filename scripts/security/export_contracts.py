"""Export Phase 1 OpenAPI and synthetic metadata examples without credentials."""

import argparse
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from backend.saas.main import create_app
from backend.shared.config import ServerSettings
from backend.shared.models import CollectorHeartbeat, IngestReceipt, MetadataPayload, Metrics, canonical_bytes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(".cicada/contracts"))
    dest = parser.parse_args().output
    dest.mkdir(parents=True, exist_ok=True)
    source_id = "src-" + "0" * 32
    identity = {
        "schema_version": 1, "tenant_id": "tenant-alpha", "collector_id": "collector-alpha-1",
        "region": "us-east-1", "source_timezone": "UTC",
    }
    timestamp = "2026-11-20T14:00:00.000000Z"
    settings = ServerSettings.model_validate({"credentials": [{
        "role": "collector", "tenant_id": identity["tenant_id"], "region": identity["region"],
        "collector_id": identity["collector_id"], "token_sha256": "0" * 64, "source_ids": [source_id],
    }]})
    app = create_app(settings, dest / "unused.sqlite")
    payload = MetadataPayload(
        **identity, policy_version="metadata-v1", payload_uuid=str(uuid5(NAMESPACE_URL, "phase1-example")),
        source_id=source_id, event_time_utc=timestamp, event_type="metric",
        metrics=Metrics(cpu_pct=24.7, service_available=True), security=None, severity="info",
    )
    receipt = IngestReceipt(
        payload_uuid=payload.payload_uuid, status="accepted",
        body_sha256=hashlib.sha256(canonical_bytes(payload)).hexdigest(),
        received_at_utc="2026-11-20T14:00:00.100000Z", analysis_status="warming_up",
    )
    beat = CollectorHeartbeat(
        **identity, heartbeat_uuid="e2b3c4d5-6789-4000-8000-abcdef123456",
        generated_at_utc=timestamp, version="0.1.0", rss_mb=64.0, cpu_pct=1.1,
        queue_depth=0, config_status="valid",
    )
    for name, data in {
        "openapi": app.openapi(), "metadata": payload.model_dump(), "heartbeat": beat.model_dump(),
        "receipt": receipt.model_dump(),
    }.items():
        (dest / f"{name}.json").write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote Phase 1 schema and metadata-only examples to {dest}")


if __name__ == "__main__":
    main()
