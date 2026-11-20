# Phase 3: design rationale and verification limits

Revised for an eight-hour, three-person prototype. This replaces the previous unsupported HIGH-confidence execution assertions. No software behavior is verified yet.

## Grounding

PDF pp.3/7 asks zero loss/duplicates after outage. Persisting only on detected failure leaves a loss window. SQLite WAL/NORMAL can lose durability on OS/power failure; use FULL and still bound claims to tested local-disk behavior. Historical sorting is distinct from online analytic ordering. A small sequential request protocol is simpler to verify than partial batch ACKs.

## Decisions

Follow the corresponding 03-01-PLAN.md and canonical CONTRACTS.md. M1 owns complex decisions; M2/M3 receive bounded artifacts. No hidden automatic agent workflow or model-specific slash command is required. External-source references and research corrections are in ../../../research.md (repository root research.md is authoritative if relative navigation differs).

## Risks and proof

Dependencies: Phase 1 identity/storage and phase 2 validated byte serialization; input and UI work stay parallel.

Evidence required: V04, V09; disk-backed restart test (never :memory:), exact ID reconciliation and unchanged analytic counts on duplicate.

All guarantees are limited to the defined fixture/fault model and demonstrated results. Unknown organizer input, production residency, actual performance and security assurance must not be called validated before measurement. See VALIDATION.md and FIX_REVIEW.md.
