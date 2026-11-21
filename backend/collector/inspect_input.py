"""
Dry-run input inspector and validation tool.

Usage:
    python -m backend.collector.inspect_input <file> [--map mapping.json/yaml]

Analyzes input telemetry files, auto-detects schema & formatting, displays
the chosen field mapping, first 5 converted RawEvent records, and diagnostic
counts of valid, malformed, or unmapped fields.

Fails loudly with non-zero exit code if file is missing, empty, or unparseable.
Never silently falls back to demo data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

from backend.collector.adapters.auto_adapter import AutoAdapter


async def inspect(file_path: Path, map_path: Path | None, tenant_id: str, collector_id: str) -> int:
    if not file_path.exists():
        sys.stderr.write(f"ERROR: Input file does not exist: {file_path}\n")
        return 1

    if file_path.is_file() and file_path.stat().st_size == 0:
        sys.stderr.write(f"ERROR: Input file is empty: {file_path}\n")
        return 1

    adapter = AutoAdapter(
        source=file_path,
        map_path=map_path,
        tenant_id=tenant_id,
        collector_id=collector_id,
    )

    events = []
    try:
        async for ev in adapter.events():
            if len(events) < 5:
                events.append(ev)
    except Exception as exc:
        sys.stderr.write(f"ERROR: Failed reading/parsing input file ({type(exc).__name__}): {exc}\n")
        return 1

    print("==========================================================================")
    print("🔍  HEIMDALL TELEMETRY INPUT INSPECTION REPORT")
    print("==========================================================================")
    print(f"Target File:        {file_path}")
    print(f"Detected Format:    {adapter.detected_format or 'unknown'}")
    print(f"Mapping Mode:       {'Configured (--map)' if map_path else 'Automatic Alias Guessing'}")
    print("--------------------------------------------------------------------------")
    print("CHOSEN FIELD MAPPING:")
    if adapter.chosen_mapping:
        for orig, target in sorted(adapter.chosen_mapping.items()):
            print(f"  • {orig} -> {target}")
    else:
        print("  (No fields mapped)")
    print("--------------------------------------------------------------------------")
    print(f"CONVERTED SAMPLE EVENTS (First {len(events)} of {adapter.total_records_read} read):")
    for idx, ev in enumerate(events, start=1):
        sample = {
            "input_id": ev.input_id,
            "source_key": ev.source_key,
            "event_time_utc": ev.event_time_utc,
            "kind": ev.kind,
            "metrics": ev.metrics,
            "auth_success": ev.auth_success,
            "source_ip": ev.source_ip,
            "username": ev.username,
        }
        print(f"[{idx}] {json.dumps(sample, indent=2)}")

    print("--------------------------------------------------------------------------")
    print("INGESTION METRICS & DIAGNOSTICS:")
    print(f"  • Total Records Read:     {adapter.total_records_read}")
    print(f"  • Valid Records Yielded:  {adapter.valid_records_yielded}")
    print(f"  • Malformed Records:      {adapter.malformed_count}")
    print(f"  • Unmapped Local Fields:  {len(adapter.unmapped_fields)} {sorted(list(adapter.unmapped_fields)) if adapter.unmapped_fields else ''}")
    print("==========================================================================")

    if adapter.valid_records_yielded == 0:
        sys.stderr.write("ERROR: Input file produced 0 valid telemetry records.\n")
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("file", type=Path, help="Telemetry input file to inspect (JSONL, JSON, CSV, TSV, or .gz)")
    parser.add_argument("--map", type=Path, default=None, help="Optional YAML/JSON field mapping file")
    parser.add_argument("--tenant", default="tenant-alpha", help="Tenant ID context (default: tenant-alpha)")
    parser.add_argument("--collector", default="collector-alpha-1", help="Collector ID context (default: collector-alpha-1)")
    args = parser.parse_args()

    sys.exit(asyncio.run(inspect(args.file, args.map, args.tenant, args.collector)))


if __name__ == "__main__":
    main()
