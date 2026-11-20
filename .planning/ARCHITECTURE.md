# Architecture and trust boundaries

## Runtime and network hops

Customer boundary:
Organizer input OR labelled demo source -> raw local event -> local security analysis -> typed sanitizer -> serialize once -> SQLite outbox -> HTTPS sender.
Raw input and outbound body -> loopback proof page only.
Approved demo command -> local simulation state -> subsequent ordinary telemetry.

SaaS boundary:
Authenticated regional ingest -> tenant-scoped SQLite metadata -> health/AIOps -> incidents/recommendations -> operator approval/audit.
React dashboard reads only metadata using two-second polling.

Every hop:
1. Organizer input to collector: transport/format confirmed at kickoff; JSONL adapter is the initial development contract.
2. Collector to SaaS HTTPS: ingest, fresh heartbeat, command polling, results, safe verification summaries.
3. Operator browser to SaaS HTTPS: metadata and approved actions.
4. Local browser to collector loopback HTTP: raw inspection and local demo controls.

SaaS never fetches raw collector data. Use separate local and central browser windows; no iframe, CORS raw-data bridge, central proxy, remote session replay or raw screenshot upload.

## Deployment

One Uvicorn SaaS process on HTTPS port 8443; built React assets served by SaaS for same-origin operation. Development Vite uses one explicitly configured localhost origin. Two collectors have separate config, HMAC keys, databases, credentials and loopback ports 9001/9002. No horizontal scaling claim.

M1 supplies development CA/server certificate SAN configuration and trust instructions. HTTPX verifies CA and hostname; never disable verification. Browser trusts CA before timing measurements. Test invalid certificate/hostname rejection. This is bearer authentication over TLS, not mTLS or payload signing.

## Identity

Credentials bind role (collector/operator), tenant, collector where applicable, and assigned region. Header/body/path must agree with authenticated identity. Query, cache, baseline, incident, source reference and action checks include tenant. Separate operator/collector credentials for each tenant. Changing a UI selector cannot grant tenant access. Topology and source membership are configured, not accepted as arbitrary event labels.

## Persistence and delivery

SaaS tables: metadata (unique tenant/UUID, actual body digest, event/receive time), fresh heartbeats, current source state, alerts (unique tenant/payload/metric/rule), incidents/membership, health transitions, proposals/commands/results, audit, render receipts and safe scenario summaries.
Local tables: outbox, receipt/audit metadata, source identity/sequence, command receipts/snapshots/demo state. Raw previews remain separately local and bounded.

Use aiosqlite, one serialized writer per process, explicit transactions, WAL and synchronous=FULL. State the tested fault model: network interruption and process restart on functioning local disk; not disk destruction or unlimited outages.

Persist every approved event BEFORE first send. Save canonical bytes and stable UUID. ACK only after server commit. Delete only that acknowledged ID. Start with one event/request, avoiding partial batch semantics. Retry network/5xx with 1/2/4/8s capped backoff plus jitter. Heartbeat/command loops must not wait for backlog draining. Default outbox cap 100 MB, configurable: pause/backpressure input and surface failure, never silently discard. Unknown non-pausable upstream loss must be reported.

Server unique (tenant_id,payload_uuid): same bytes -> duplicate ACK; different digest -> 409 conflict. Persist metadata and uniquely keyed analytic effects in one serialized transaction before ACK for MVP. Compute proposed analytic updates without mutating live cache until commit. On restart rebuild baseline caches from committed eligible metadata. A duplicate must not regenerate alerts, incidents or actions.

Raw local preview retention: max 500 records or 15 minutes, whichever first; timer purge and local file permissions. Use smaller limits in tests. Do not log bearer tokens or raw bodies into central diagnostics.

## Event time and freshness

Preserve timezone-aware UTC and IANA source timezone. Historical queries sort by event_time then UUID. MVP late policy: events with time <= latest analyzed source time are stored historically and do not re-run live analysis. Explain this limitation; historical anomaly recomputation is deferred. Latest source metrics use greatest event time.

Only a validated fresh heartbeat updates collector liveness. Old replayed telemetry does not update source freshness or make the collector online. Reject future event timestamps beyond configurable 5s skew. Historical organizer replays form a separate timing cohort; do not rewrite source timestamps to manufacture latency compliance.

## Simulation commands

M3 supplies a pure demo source with memory demand/capacity, snapshot and restore. M1 owns policy, authenticated outbound collector polling, persistent command idempotency and snapshot handling. Allow only SCALE_CONTAINER_MEMORY for a configured demo target. No shell execution. Approve queues a command; successful collector result and subsequent telemetry demonstrate effect. Rollback restores the saved capacity. Persist snapshot, demo state and command receipt atomically. Only one active action per target. Organizer/live sources cannot execute demo remediation.

## Regions and scale

MVP validates tenant assigned-region policy on one local deployment. Real residency requires separate regional compute/storage/backups and controlled replication; URL paths do not establish geography. Future scaling uses region/tenant partitioning, durable queues, database uniqueness and bounded event-time processing. Document, do not implement, this infrastructure.
