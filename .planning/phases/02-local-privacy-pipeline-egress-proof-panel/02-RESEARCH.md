# Phase 2: Local Privacy Pipeline & Egress Proof Panel — Research

**Researched:** 2026-11-20
**Domain:** Edge Data Protection, Regular Expression Secret Scrubbing, Field Allow-Listing, Cryptographic Pseudonymization, Egress Audit Logging
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- Zero Data Exposure: Raw logs, passwords, API tokens, connection strings, and sensitive payloads must NEVER cross the local collector boundary.
- Strict Allow-Listing: Egress payload serializer must reject any property not explicitly listed in `APPROVED_METADATA_FIELDS`.
- Egress Proof Panel: Dedicated local UI running on collector host (e.g. `http://localhost:9001`) that displays side-by-side: `[Raw Local Event with Detected Secret]` vs. `[Redacted Allow-Listed Egress Payload]`.
- Source Pseudonymization: Local hostnames and IPs must be pseudonymized (e.g., `prod-db-01.internal` → `node_h8f3a9`, `192.168.1.42` → `net_anon_3a`) consistently using HMAC-SHA256 with a local salt.

### Claude's Discretion
- Scrubbing Engine: High-speed compiled regex patterns matching AWS access keys (`AKIA...`), generic API keys, Bearer tokens, DB connection URIs (`postgres://user:pass@...`), and common password patterns.
- Egress Proof Panel Server: Lightweight local FastAPI or built-in Python HTTP server serving an HTML/JS audit console.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| Secret Scrubber (Regex Engine) | Tier 1 (Customer Edge) | — | Must scrub content before serialization or network socket writes |
| Field Allow-Lister | Tier 1 (Customer Edge) | Tier 2 (Gateway Validation) | Drops unknown fields locally; SaaS rejects unapproved fields as defense-in-depth |
| Identifier Pseudonymizer | Tier 1 (Customer Edge) | — | Keeps raw infrastructure topologies and internal IPs within the enterprise |
| Egress Proof Panel Web UI | Tier 1 (Customer Edge) | — | Local inspector view for security officers & judges to audit outgoing packets |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 2 builds the core differentiator and compliance center of the Cicada platform. Rather than filtering telemetry in the cloud (which breaks compliance the second packets leave the firewall), all scrubbing, pseudonymization, and filtering happen inside Tier 1:
1. **Multi-Stage Sanitization Pipeline**:
   - `Ingest`: Accepts raw OS, syslog, or simulated telemetry records.
   - `Secret Scrubber`: Executes compiled regex suites targeting passwords, bearer tokens, AWS/GCP/SSH keys, credit cards, and private URIs. Replaces with `[REDACTED_SECRET:<TYPE>]`.
   - `Pseudonymizer`: Deterministically hashes internal node names and IPs using a local private salt (`HMAC-SHA256`) so time-series identity is preserved across restarts without leaking real names.
   - `Allow-List Serializer`: Constructs the `MetadataPayload` by extracting only explicitly whitelisted keys (`timestamp_utc`, `source_id`, `metrics`, `event_type`, `severity`, `risk_score`).
2. **Egress Proof Panel**:
   - Maintains an append-only in-memory and local SQLite audit log of the last 1000 transmissions.
   - Serves an interactive local web interface displaying the exact raw record alongside the scrubbed egress JSON with high-contrast redaction badges, allowing judges to test Scenario 1 ("Raw log contains a secret") live.
</research_summary>

## Key Implementation Patterns
- `re.compile()` regex catalog covering OWASP secret patterns.
- HMAC-based salted hashing for reversible-locally, opaque-remotely source tokens.
- Live WebSocket / SSE stream from local collector daemon to local Egress Proof UI.
