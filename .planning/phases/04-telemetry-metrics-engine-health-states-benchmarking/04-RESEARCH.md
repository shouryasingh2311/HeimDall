# Phase 4: design rationale and verification limits

Revised for an eight-hour, three-person prototype. This replaces the previous unsupported HIGH-confidence execution assertions. No software behavior is verified yet.

## Grounding

PDF pp.3/8 defines targets and health states but illustrative thresholds are not universal. Proposed concrete thresholds are configurable prototype rules. The PDF's targets need organizer confirmation. Watchdog intervals count toward offline latency. A dashboard measurement needs browser instrumentation and synchronized/characterized clocks.

## Decisions

Follow the corresponding 04-01-PLAN.md and canonical CONTRACTS.md. M1 owns complex decisions; M2/M3 receive bounded artifacts. No hidden automatic agent workflow or model-specific slash command is required. External-source references and research corrections are in ../../../research.md (repository root research.md is authoritative if relative navigation differs).

## Risks and proof

Dependencies: Contracts, durable ingest and heartbeat path. M2 can implement display/timing against fixtures before live connection.

Evidence required: V05, V07, V10; working targets 10s p95 render, 15s alert, 60s offline. Stop heartbeat separately from a 30s outage scenario.

All guarantees are limited to the defined fixture/fault model and demonstrated results. Unknown organizer input, production residency, actual performance and security assurance must not be called validated before measurement. See VALIDATION.md and FIX_REVIEW.md.
