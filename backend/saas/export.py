"""
SaaS Data Export Engine & CLI.

Supports exporting allow-listed metadata for a tenant over an optional time range:
- Metrics: CSV and JSON
- Health Transitions: CSV and JSON
- Incidents (with Evidence Score, Baselines, Z-Scores, Remediation): JSON and Markdown Report
- Remediation Audit Log: CSV and JSON
- Complete ZIP export bundle for single-click downloads

Security Invariant:
Only exports allow-listed metadata already held by SaaS. Never raw inputs or secrets.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple
import zipfile

import aiosqlite

from backend.shared.models import MetadataPayload, utc_now, utc_text


async def fetch_metrics_data(
    db: aiosqlite.Connection,
    tenant_id: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = [
        "SELECT payload_uuid, source_id, event_time, received_at, body_sha256, body",
        "FROM metadata WHERE tenant_id = ? AND event_type = 'metric'",
    ]
    params: List[Any] = [tenant_id]

    if from_time:
        query.append("AND event_time >= ?")
        params.append(from_time)
    if to_time:
        query.append("AND event_time <= ?")
        params.append(to_time)

    query.append("ORDER BY event_time ASC, payload_uuid ASC")

    rows = await db.execute_fetchall(" ".join(query), params)
    records = []
    for row in rows:
        try:
            body = json.loads(row["body"])
            metrics = body.get("metrics") or {}
        except Exception:
            metrics = {}

        records.append({
            "payload_uuid": row["payload_uuid"],
            "source_id": row["source_id"],
            "event_time_utc": row["event_time"],
            "received_at_utc": row["received_at"],
            "body_sha256": row["body_sha256"],
            "cpu_pct": metrics.get("cpu_pct"),
            "memory_pct": metrics.get("memory_pct"),
            "disk_used_pct": metrics.get("disk_used_pct"),
            "latency_ms": metrics.get("latency_ms"),
            "packet_loss_pct": metrics.get("packet_loss_pct"),
            "net_tx_bps": metrics.get("net_tx_bps"),
            "net_rx_bps": metrics.get("net_rx_bps"),
            "service_available": metrics.get("service_available"),
            "connectivity": metrics.get("connectivity"),
        })
    return records


async def fetch_transitions_data(
    db: aiosqlite.Connection,
    tenant_id: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = [
        "SELECT id, entity_type, entity_id, from_state, to_state, reasons, observed_at",
        "FROM health_transition WHERE tenant_id = ?",
    ]
    params: List[Any] = [tenant_id]

    if from_time:
        query.append("AND observed_at >= ?")
        params.append(from_time)
    if to_time:
        query.append("AND observed_at <= ?")
        params.append(to_time)

    query.append("ORDER BY id ASC")

    rows = await db.execute_fetchall(" ".join(query), params)
    transitions = []
    for row in rows:
        reasons_parsed = []
        try:
            reasons_parsed = json.loads(row["reasons"])
        except Exception:
            reasons_parsed = [row["reasons"]]

        transitions.append({
            "id": row["id"],
            "entity_type": row["entity_type"],
            "entity_id": row["entity_id"],
            "from_state": row["from_state"],
            "to_state": row["to_state"],
            "reasons": reasons_parsed,
            "observed_at_utc": row["observed_at"],
        })
    return transitions


async def fetch_incidents_data(
    db: aiosqlite.Connection,
    tenant_id: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = [
        "SELECT id, incident_id, group_key, category, severity, status, created_at, last_event",
        "FROM incident WHERE tenant_id = ?",
    ]
    params: List[Any] = [tenant_id]

    if from_time:
        query.append("AND created_at >= ?")
        params.append(from_time)
    if to_time:
        query.append("AND created_at <= ?")
        params.append(to_time)

    query.append("ORDER BY id DESC")

    rows = await db.execute_fetchall(" ".join(query), params)
    incidents = []

    for r in rows:
        inc_id = r["incident_id"]

        # Fetch associated alerts
        alert_rows = await db.execute_fetchall(
            """SELECT id, payload_uuid, source_id, metric, observed, baseline_mean, baseline_std, z_score, event_time, breach_at
               FROM alert WHERE tenant_id = ? AND incident_id = ? ORDER BY event_time ASC""",
            (tenant_id, inc_id),
        )
        alerts = [dict(a) for a in alert_rows]

        # Fetch affected sources
        src_rows = await db.execute_fetchall(
            "SELECT source_id, normal_count, last_normal FROM incident_source WHERE tenant_id = ? AND incident_id = ?",
            (tenant_id, inc_id),
        )
        sources = [s["source_id"] for s in src_rows] or list(set(a["source_id"] for a in alerts))

        # Fetch associated action / proposal
        action_rows = await db.execute_fetchall(
            """SELECT action_id, source_id, status, reason_code, created_at
               FROM demo_action WHERE tenant_id = ? AND incident_id = ?""",
            (tenant_id, inc_id),
        )
        proposal = dict(action_rows[0]) if action_rows else None

        # Evidence scoring calculation: 30 * min(metrics, 2) + 20 * dependency + 20 * temporal
        metric_types = set(a["metric"] for a in alerts)
        evidence_score = min(100, 30 * min(len(metric_types), 2) + (20 if len(sources) > 1 else 0) + (20 if len(alerts) >= 2 else 0))
        if evidence_score == 0 and alerts:
            evidence_score = 60

        incidents.append({
            "incident_id": inc_id,
            "category": r["category"],
            "severity": r["severity"],
            "status": r["status"],
            "created_at_utc": r["created_at"],
            "last_event_utc": r["last_event"],
            "affected_sources": sorted(sources),
            "evidence_score": evidence_score,
            "score_method": "heuristic_30m_20d_20t",
            "alerts": alerts,
            "proposal": proposal,
        })

    return incidents


async def fetch_remediation_audit(
    db: aiosqlite.Connection,
    tenant_id: str,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = [
        "SELECT id, action_id, actor, previous_status, status, policy_verdict, reason_code, occurred_at",
        "FROM demo_audit WHERE tenant_id = ?",
    ]
    params: List[Any] = [tenant_id]

    if from_time:
        query.append("AND occurred_at >= ?")
        params.append(from_time)
    if to_time:
        query.append("AND occurred_at <= ?")
        params.append(to_time)

    query.append("ORDER BY id ASC")

    rows = await db.execute_fetchall(" ".join(query), params)
    return [dict(row) for row in rows]


def to_csv_string(rows: List[Dict[str, Any]], fieldnames: List[str]) -> str:
    """Serialize list of dicts to RFC 4180 CSV string."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        # Flatten list/dict values if needed
        clean_row = {}
        for k, v in row.items():
            if isinstance(v, (list, dict)):
                clean_row[k] = json.dumps(v)
            else:
                clean_row[k] = "" if v is None else str(v)
        writer.writerow(clean_row)
    return buf.getvalue()


def generate_incident_markdown(incidents: List[Dict[str, Any]], tenant_id: str) -> str:
    """Generate decision-grade human-readable Markdown incident report."""
    md = [
        "# 🛡️ Heimdall AIOps Incident & Threat Report",
        "",
        f"> **Tenant Context:** `{tenant_id}`  ",
        f"> **Generated At (UTC):** `{utc_text(utc_now())}`  ",
        f"> **Total Incidents Recorded:** {len(incidents)}",
        "",
        "---",
        "",
        "## 1. Executive Summary",
        "",
        "| Incident ID | Severity | Status | Score | Created (UTC) | Affected Sources |",
        "| :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for inc in incidents:
        inc_id = inc.get("incident_id") or inc.get("id") or "unknown"
        sev = str(inc.get("severity", "MEDIUM")).upper()
        status = inc.get("status", "OPEN")
        score = inc.get("evidence_score", 0)
        created = inc.get("created_at_utc", "N/A")
        sources_list = inc.get("affected_sources", [])
        sources_str = ", ".join(f"`{s}`" for s in sources_list) if sources_list else "`*`"
        md.append(f"| `{inc_id}` | **{sev}** | `{status}` | `{score} / 100` | `{created}` | {sources_str} |")

    md.extend([
        "",
        "---",
        "",
        "## 2. Incident Investigation & Anomaly Signals",
        "",
    ])

    for inc in incidents:
        inc_id = inc.get("incident_id") or inc.get("id") or "unknown"
        sev = str(inc.get("severity", "MEDIUM")).upper()
        cat = inc.get("category", "SYSTEM_ALERT")
        status = inc.get("status", "OPEN")
        created = inc.get("created_at_utc", "N/A")
        last_ev = inc.get("last_event_utc", created)
        score = inc.get("evidence_score", 0)
        method = inc.get("score_method", "HEURISTIC")
        md.extend([
            f"### Incident: `{inc_id}`",
            f"- **Severity:** `{sev}` | **Category:** `{cat}` | **Status:** `{status}`",
            f"- **Created:** `{created}` | **Last Event:** `{last_ev}`",
            f"- **Heuristic Evidence Score:** **`{score} / 100`** *(Method: `{method}`)*",
        ])

        if inc.get("title"):
            md.append(f"- **Title:** {inc['title']}")
        if inc.get("summary"):
            md.append(f"- **Summary:** {inc['summary']}")
        if inc.get("recommended_action"):
            md.append(f"- **Recommended Action:** `{inc['recommended_action']}`")
        if inc.get("baseline") is not None:
            md.append(f"- **Baseline:** `{inc['baseline']}`")
        if inc.get("z_score") is not None:
            md.append(f"- **Anomaly z-Score:** `{inc['z_score']}`")

        md.extend([
            "",
            "#### Statistical Metric Signals & Baseline Breaches:",
            r"| Source Pseudonym | Metric | Observed | Baseline Mean ($\mu$) | Std Dev ($\sigma$) | $z$-Score | Breach Time (UTC) |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        alerts = inc.get("alerts") or []
        if alerts:
            for a in alerts:
                b_mean = f"{a['baseline_mean']:.2f}" if a.get('baseline_mean') is not None else "N/A"
                b_std = f"{a['baseline_std']:.2f}" if a.get('baseline_std') is not None else "N/A"
                z_sc = f"{a['z_score']:.2f}" if a.get('z_score') is not None else "N/A"
                obs = f"{a['observed']:.2f}" if a.get('observed') is not None else "N/A"
                md.append(f"| `{a.get('source_id')}` | `{a.get('metric')}` | `{obs}` | {b_mean} | {b_std} | **`{z_sc}`** | `{a.get('breach_at')}` |")
        else:
            md.append("| *(No individual metric breach records)* | - | - | - | - | - | - |")

        if inc.get("proposal"):
            prop = inc["proposal"]
            md.extend([
                "",
                "#### Autonomous Remediation Action:",
                f"- **Action ID:** `{prop['action_id']}`",
                f"- **Playbook:** `SCALE_CONTAINER_MEMORY` *(Factor: 1.5x)*",
                f"- **Target Source:** `{prop['source_id']}`",
                f"- **Lifecycle Status:** `{prop['status']}`",
                f"- **Policy Verdict:** `{prop['reason_code']}`",
            ])

        md.extend(["", "---", ""])

    return "\n".join(md)


def build_export_zip(
    metrics_records: List[Dict[str, Any]],
    transitions_records: List[Dict[str, Any]],
    incidents_records: List[Dict[str, Any]],
    remediation_records: List[Dict[str, Any]],
    tenant_id: str,
) -> bytes:
    """Create in-memory ZIP bundle containing all export artifacts."""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        # 1. Metrics CSV & JSON
        metric_fields = [
            "payload_uuid", "source_id", "event_time_utc", "received_at_utc", "body_sha256",
            "cpu_pct", "memory_pct", "disk_used_pct", "latency_ms", "packet_loss_pct",
            "net_tx_bps", "net_rx_bps", "service_available", "connectivity"
        ]
        zf.writestr("metrics.csv", to_csv_string(metrics_records, metric_fields))
        zf.writestr("metrics.json", json.dumps(metrics_records, indent=2))

        # 2. Health transitions CSV & JSON
        transition_fields = ["id", "entity_type", "entity_id", "from_state", "to_state", "reasons", "observed_at_utc"]
        zf.writestr("transitions.csv", to_csv_string(transitions_records, transition_fields))
        zf.writestr("transitions.json", json.dumps(transitions_records, indent=2))

        # 3. Incidents JSON & Markdown report
        zf.writestr("incidents.json", json.dumps(incidents_records, indent=2))
        zf.writestr("incident_report.md", generate_incident_markdown(incidents_records, tenant_id))

        # 4. Remediation Audit CSV & JSON
        audit_fields = ["id", "action_id", "actor", "previous_status", "status", "policy_verdict", "reason_code", "occurred_at"]
        zf.writestr("remediation_audit.csv", to_csv_string(remediation_records, audit_fields))
        zf.writestr("remediation_audit.json", json.dumps(remediation_records, indent=2))

    return zip_buffer.getvalue()


async def run_cli_export(
    tenant_id: str,
    output_dir: Path,
    runtime: Path,
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
) -> int:
    db_path = runtime / "saas.sqlite"
    if not db_path.exists():
        sys.stderr.write(f"ERROR: SaaS database not found at {db_path}\n")
        return 1

    output_dir.mkdir(parents=True, exist_ok=True)

    async with aiosqlite.connect(db_path) as db:
        db.row_factory = aiosqlite.Row

        metrics = await fetch_metrics_data(db, tenant_id, from_time, to_time)
        transitions = await fetch_transitions_data(db, tenant_id, from_time, to_time)
        incidents = await fetch_incidents_data(db, tenant_id, from_time, to_time)
        remediation = await fetch_remediation_audit(db, tenant_id, from_time, to_time)

        # Write Metrics
        metric_fields = [
            "payload_uuid", "source_id", "event_time_utc", "received_at_utc", "body_sha256",
            "cpu_pct", "memory_pct", "disk_used_pct", "latency_ms", "packet_loss_pct",
            "net_tx_bps", "net_rx_bps", "service_available", "connectivity"
        ]
        (output_dir / "metrics.csv").write_text(to_csv_string(metrics, metric_fields), encoding="utf-8")
        (output_dir / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

        # Write Transitions
        trans_fields = ["id", "entity_type", "entity_id", "from_state", "to_state", "reasons", "observed_at_utc"]
        (output_dir / "transitions.csv").write_text(to_csv_string(transitions, trans_fields), encoding="utf-8")
        (output_dir / "transitions.json").write_text(json.dumps(transitions, indent=2), encoding="utf-8")

        # Write Incidents & Report
        (output_dir / "incidents.json").write_text(json.dumps(incidents, indent=2), encoding="utf-8")
        (output_dir / "incident_report.md").write_text(generate_incident_markdown(incidents, tenant_id), encoding="utf-8")

        # Write Remediation Audit
        audit_fields = ["id", "action_id", "actor", "previous_status", "status", "policy_verdict", "reason_code", "occurred_at"]
        (output_dir / "remediation_audit.csv").write_text(to_csv_string(remediation, audit_fields), encoding="utf-8")
        (output_dir / "remediation_audit.json").write_text(json.dumps(remediation, indent=2), encoding="utf-8")

    print("==========================================================================")
    print("📦  HEIMDALL METADATA EXPORT COMPLETE")
    print("==========================================================================")
    print(f"Tenant Context:       {tenant_id}")
    print(f"Target Directory:     {output_dir}")
    print(f"Exported Metrics:     {len(metrics)} records -> metrics.csv, metrics.json")
    print(f"Health Transitions:   {len(transitions)} records -> transitions.csv, transitions.json")
    print(f"AIOps Incidents:      {len(incidents)} records -> incidents.json, incident_report.md")
    print(f"Remediation Audits:   {len(remediation)} records -> remediation_audit.csv, remediation_audit.json")
    print("Security Guarantee:   100% allow-listed metadata only. Zero raw secrets exported.")
    print("==========================================================================")
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", required=True, help="Tenant ID (e.g. tenant-alpha)")
    parser.add_argument("--output-dir", type=Path, default=Path("export"), help="Destination directory for export files")
    parser.add_argument("--runtime", type=Path, default=Path(".heimdal/demo"), help="Runtime path to locate saas.sqlite")
    parser.add_argument("--from", dest="from_time", help="Optional ISO UTC start time (e.g. 2026-11-20T00:00:00Z)")
    parser.add_argument("--to", dest="to_time", help="Optional ISO UTC end time (e.g. 2026-11-21T00:00:00Z)")
    args = parser.parse_args()

    sys.exit(asyncio.run(run_cli_export(args.tenant, args.output_dir, args.runtime, args.from_time, args.to_time)))


if __name__ == "__main__":
    main()
