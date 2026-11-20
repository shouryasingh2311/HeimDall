# Research corrections and scoped design rationale

This revision replaces the earlier overconfident competitor matrix and unsupported absolute claims. It supports an eight-hour prototype; it does not certify uniqueness or production suitability.

## What is established

The supplied evaluation PDF requires local-first processing, metadata-only SaaS, tenant separation, four health states, AIOps explanations, reliability/timing evidence, the common organizer stream and an egress panel. Its eight scenarios are behavior checks, not a requirement for a bespoke chaos platform. Autonomous execution may be simulated; real operations are future work.

## Corrections to previous research

- Local filtering/redaction is not a new invention. Datadog documents agent-side masking; do not say its architecture necessarily ships all secrets unchanged. [Datadog agent rules](https://docs.datadoghq.com/agent/logs/advanced_log_collection/#scrub-sensitive-data-from-your-logs)
- Before/after pipeline previews already exist. Cribl documents IN/OUT views; this does not establish equivalence to our entire evidence workflow, but prevents blanket claims that nobody offers visual transformation inspection. [Cribl preview](https://docs.cribl.io/stream/data-preview/)
- Do not call VRL Turing-complete. Its documentation describes no user-defined recursion or unbounded loops. [VRL](https://vector.dev/docs/reference/vrl/)
- WAL/NORMAL is not full durability against power/OS failure. The prototype chooses FULL, with claims still bounded by tested faults and functioning storage. [SQLite synchronous](https://sqlite.org/pragma.html#pragma_synchronous)
- Outer schema validation does not define arbitrary nested dictionary contents. Use explicit nested models and forbid unknown fields. [Pydantic models](https://docs.pydantic.dev/latest/concepts/models/)
- TLS needs real certificate/server/trust setup, not merely an HTTP client library. [FastAPI HTTPS](https://fastapi.tiangolo.com/deployment/https/)
- Vite supports React/TypeScript scaffolding and a static build suitable for our small client. Check current Node requirements when freezing dependencies. [Vite guide](https://vite.dev/guide/)

## Prototype choices

One rolling statistical detector and deterministic explanations avoid external model latency and unsupported causal claims. One persisted outbox with unique server records is easier to verify than a distributed broker. Two-second polling avoids unnecessary streaming infrastructure. One pure demo action with saved-state restoration satisfies the safe-simulation scenario.

Metadata receipt matching and payload-linked explanations are the proposed presentation differentiator. A market-wide uniqueness assertion has not been established. No broad competitor feature matrix, arbitrary 28+ verified-source claim, 100% explainability guarantee, fixed alert-reduction target or global production readiness claim is retained.

## Outstanding research inputs

Actual organizer stream schema/transport, final target values, available runtime versions, team familiarity and measured load/performance. Phase research files are design rationale, not independent experiments. Revisit assumptions using observed implementation evidence.
