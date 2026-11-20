# Phase 5: design rationale and verification limits

Revised for an eight-hour, three-person prototype. This replaces the previous unsupported HIGH-confidence execution assertions. No software behavior is verified yet.

## Grounding

PDF pp.6-7/9 values context, correlation and explainability beyond static thresholds. A rolling z-score is explainable but not a seasonal or causal model. Mean/std must be computed before updating with candidate. Hard-coded confidence percentages and arbitrary broad grouping undermine trust. The MVP explicitly limits late analysis and uses configured dependencies.

## Decisions

Follow the corresponding 05-01-PLAN.md and canonical CONTRACTS.md. M1 owns complex decisions; M2/M3 receive bounded artifacts. No hidden automatic agent workflow or model-specific slash command is required. External-source references and research corrections are in ../../../research.md (repository root research.md is authoritative if relative navigation differs).

## Risks and proof

Dependencies: Phases 2-4 contracts/ingest/time rules. M3 supplies seeded datasets and M2 prepares evidence UI concurrently.

Evidence required: V06, V08; score/explanation reproducible from actual incident members. Report false alerts on normal control; do not assert perfection.

All guarantees are limited to the defined fixture/fault model and demonstrated results. Unknown organizer input, production residency, actual performance and security assurance must not be called validated before measurement. See VALIDATION.md and FIX_REVIEW.md.
