# Phase 6: design rationale and verification limits

Revised for an eight-hour, three-person prototype. This replaces the previous unsupported HIGH-confidence execution assertions. No software behavior is verified yet.

## Grounding

PDF pp.8-10 treats real autonomous operations as future work and accepts safe simulation. Snapshot restoration of a virtual resource is defensible; exact inverse service restart is not. Pseudonymous metadata cannot justify a real IP/PID command. Central state decoration is not proof of recovery; source-generated telemetry is required.

## Decisions

Follow the corresponding 06-01-PLAN.md and canonical CONTRACTS.md. M1 owns complex decisions; M2/M3 receive bounded artifacts. No hidden automatic agent workflow or model-specific slash command is required. External-source references and research corrections are in ../../../research.md (repository root research.md is authoritative if relative navigation differs).

## Risks and proof

Dependencies: Phase 5 incident API, phase 1 roles/commands and M3 demo source. M2 builds pending/action UI early.

Evidence required: V02, V11; one fully proven simulated action is sufficient for scenario 8.

All guarantees are limited to the defined fixture/fault model and demonstrated results. Unknown organizer input, production residency, actual performance and security assurance must not be called validated before measurement. See VALIDATION.md and FIX_REVIEW.md.
