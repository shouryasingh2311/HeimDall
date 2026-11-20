# Phase 3: Resilient Offline Buffering & Idempotent Ingestion — Research

**Researched:** 2026-11-20
**Domain:** Crash-Resilient Local Storage (SQLite WAL), Dead-Letter Queues, Exponential Backoff, Idempotent De-Duplication, Out-of-Order Event Time Indexing
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- Zero Loss Post-Outage: When SaaS is down or unreachable, 100% of approved metadata records must be buffered locally and delivered upon reconnect.
- Zero Duplicates Post-Outage: Reconnect delivery retries must never create duplicate records or skew metric trends.
- Idempotent Ingestion: Every payload carries a deterministic UUID. SaaS checks seen payload UUIDs in an indexed de-duplication store.
- Out-of-Order Handling: Events carry UTC event timestamps. Time-series indexing places points by `timestamp_utc`, never by `arrival_time`.

### Claude's Discretion
- Local Buffer Store: SQLite database with `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` for high-throughput zero-corruption disk spooling.
- De-duplication Cache: In-memory sliding set (e.g., Redis or in-memory LRU set with SQLite persistence) storing recent UUIDs with a 24-hour TTL.
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| Local Offline Buffer (SQLite WAL) | Tier 1 (Customer Edge) | — | Must persist to local disk so daemon restarts or system reboots do not lose data |
| Outage Detector & Backoff Scheduler | Tier 1 (Customer Edge) | — | Tracks SaaS connectivity health, pauses outgoing HTTP calls, triggers exponential backoff |
| Backlog Drain Worker | Tier 1 (Customer Edge) | Tier 2 (SaaS Ingest) | Drains buffered rows in sequential batches with explicit HTTP 200/207 ACK before deleting |
| Idempotency De-duplication Filter | Tier 2 (Central SaaS) | — | Checks incoming `payload_uuid` against deduplication index; returns 200 ACK for duplicates without storing |
| Event-Time Timeseries Sorter | Tier 2 (Central SaaS) | Dashboard Layer | Stores points by UTC event timestamp; sorts queries by event time so late points don't disrupt graphs |
</architectural_responsibility_map>

<research_summary>
## Summary

Phase 3 implements the delivery reliability engine, which accounts for 10 of the 35 marks in Checkpoint 3. The architecture guarantees zero data loss and zero duplicates during network partitions:
1. **Tier 1 Local Buffer Queue (`buffer.db`)**:
   - Built on SQLite in Write-Ahead-Logging (WAL) mode.
   - When the HTTP transport detects a connection failure or HTTP 5xx error, it toggles to `OFFLINE_BUFFERING` state.
   - Payloads are inserted with auto-incrementing sequential sequence numbers, state (`PENDING`), and payload JSON.
   - When SaaS health checks succeed, a drainage loop sends batches of up to 50 records. Only after receiving an explicit HTTP 200 ACK from SaaS are the batch records marked `DELIVERED` and pruned.
2. **Tier 2 Idempotency & Out-of-Order Engine**:
   - SaaS maintains a deduplication index of `payload_uuid`.
   - If a network ACK was lost and the collector retries an already-processed batch, SaaS identifies the duplicate UUID, acknowledges the receipt, and skips ingestion without duplicating metric points.
   - All time-series insertions and window aggregations are indexed by `timestamp_utc`, ensuring late-arriving packets slot into the correct historical interval.
</research_summary>

## Key Implementation Patterns
- SQLite WAL mode for concurrency and durability.
- Batch drain with transactional delete-on-ACK.
- Fast hash-set de-duplication on SaaS ingress.
