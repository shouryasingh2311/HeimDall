# Phase 7: design rationale and verification limits

Revised for an eight-hour, three-person prototype. This replaces the previous unsupported HIGH-confidence execution assertions. No software behavior is verified yet.

## Grounding

PDF pp.5/9-10 mandates common stream and live scenario reactions, not one-click UI or a custom simulation platform. A fault injector is useful only when normal processing generates outcomes. Organizer integration remains unverified until a real stream example is tested. Local triggering simplifies trust boundaries.

## Decisions

Follow the corresponding 07-01-PLAN.md and canonical CONTRACTS.md. M1 owns complex decisions; M2/M3 receive bounded artifacts. No hidden automatic agent workflow or model-specific slash command is required. External-source references and research corrections are in ../../../research.md (repository root research.md is authoritative if relative navigation differs).

## Risks and proof

Dependencies: Start input fixtures at G0, do not wait for phase 6. Each scenario activates when its backend capability is available.

Evidence required: V00 and V03-V12; all eight scenario behaviors, plus negative controls; no instant fabricated PASS.

All guarantees are limited to the defined fixture/fault model and demonstrated results. Unknown organizer input, production residency, actual performance and security assurance must not be called validated before measurement. See VALIDATION.md and FIX_REVIEW.md.
