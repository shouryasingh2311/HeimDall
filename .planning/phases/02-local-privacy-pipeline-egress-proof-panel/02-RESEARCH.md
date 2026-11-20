# Phase 2: design rationale and verification limits

Revised for an eight-hour, three-person prototype. This replaces the previous unsupported HIGH-confidence execution assertions. No software behavior is verified yet.

## Grounding

PDF pp.3/7 requires exact egress payload inspection and raw data local only. Side-by-side windows satisfy this without a central raw bridge. Ordinary audit rows are application history, not tamper evidence. HMAC is one-way; local reversal needs a mapping. Fields accepted by a parent schema do not automatically constrain nested dictionaries.

## Decisions

Follow the corresponding 02-01-PLAN.md and canonical CONTRACTS.md. M1 owns complex decisions; M2/M3 receive bounded artifacts. No hidden automatic agent workflow or model-specific slash command is required. External-source references and research corrections are in ../../../research.md (repository root research.md is authoritative if relative navigation differs).

## Risks and proof

Dependencies: Phase 1 contracts/runtime; can develop alongside phases 3/8 after schema freeze.

Evidence required: V03; same UUID/body digest on actual send and receive, negative privacy fixtures, local API protection and retention.

All guarantees are limited to the defined fixture/fault model and demonstrated results. Unknown organizer input, production residency, actual performance and security assurance must not be called validated before measurement. See VALIDATION.md and FIX_REVIEW.md.
