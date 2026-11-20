# Phase 8: design rationale and verification limits

Revised for an eight-hour, three-person prototype. This replaces the previous unsupported HIGH-confidence execution assertions. No software behavior is verified yet.

## Grounding

PDF pp.5/7/10 explicitly rejects polished screens without working processing. Frontend contributes evidence but does not own all 65 implementation/demo marks. Two-second polling is enough to target <=10s with measured processing budget. Browser timing and honest failure states matter more than WebSockets/animations.

## Decisions

Follow the corresponding 08-01-PLAN.md and canonical CONTRACTS.md. M1 owns complex decisions; M2/M3 receive bounded artifacts. No hidden automatic agent workflow or model-specific slash command is required. External-source references and research corrections are in ../../../research.md (repository root research.md is authoritative if relative navigation differs).

## Risks and proof

Dependencies: React scaffold starts after G0; each screen consumes phase APIs as available. Not blocked on completion of phase 7.

Evidence required: V03, V05, V08, V10, V11, V12, V13; live build and clean-start rehearsal.

All guarantees are limited to the defined fixture/fault model and demonstrated results. Unknown organizer input, production residency, actual performance and security assurance must not be called validated before measurement. See VALIDATION.md and FIX_REVIEW.md.
