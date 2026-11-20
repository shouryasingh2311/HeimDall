# Phase 1 implementation and evidence

The collector and SaaS run separately. Bootstrap generates two tenant scopes and a local HTTPS certificate. The collector reads Member 3's inputs, builds typed metadata, derives stable pseudonyms and UUIDs, and checks the SaaS receipt against the outbound bytes. The SaaS enforces credential roles, tenant, collector, source, and assigned region. It commits approved metadata to SQLite before acknowledging. Setup and schema export commands are in [the Phase 1 runbook](../../../docs/PHASE1.md).

| Check | Observed result |
|---|---|
| V00 | Local and demo inputs were exercised. Official organizer stream and compatibility remain pending. |
| V01 | Two processes communicated over verified HTTPS. Wrong CA, hostname and credential were rejected. |
| V02 | Implemented ingest and read paths denied cross-tenant credentials, forged identity/scope, and wrong roles. Later action/subscription routes are outside this slice. |
| V03 happy path | Actual collector preview and SaaS receipt share the same UUID and digest. Central reads contained approved data, and the local preview required its own session token. |
| G1 live render | Edge rendered an actual SaaS receipt in Member 2's build at 1d90f88. The browser harness used generated operator credentials and a CA-verified transport. The standard operator credential flow remains a dashboard handoff item. |

Verification ran on 2026-11-20 using the synthetic test input. Python suite passed 21 tests, including three process-based Phase 1 tests and the Edge assertion. The dashboard built and passed four client checks. The dependency check passed and OpenAPI plus synthetic examples were generated. Review the scoped acceptance evidence before marking V00 or G1 complete.
