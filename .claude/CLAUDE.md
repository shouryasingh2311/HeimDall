<!-- GSD:project-start source:PROJECT.md -->

## Project

**Cicada AIOps Observability Platform**

Cicada is an end-to-end, privacy-first AIOps observability platform designed to monitor distributed enterprise, data center, cloud, and edge infrastructures without exposing sensitive operational data outside customer environments. Using a two-tier architecture, a lightweight local collector gathers telemetry, performs local filtering, secret scrubbing, and local threat analysis, and transmits strictly allow-listed metadata to a centralized multi-tenant SaaS platform that delivers explainable AIOps anomaly detection, alert correlation, and policy-governed autonomous remediation workflows.

**Core Value:** Zero raw telemetry or credentials leave the customer environment, verified by a local Egress Proof Panel, while the SaaS platform delivers real-time, explainable AIOps correlation and actionable operational recommendations.

### Constraints

- **Timeline**: 24-hour hackathon execution window.
- **Security**: Zero raw logs, secrets, or unapproved fields may cross the network boundary.
- **Portability**: Must be deployable anywhere as lightweight, self-contained runtimes (Python/Node/Docker).
- **Compliance**: Tenant isolation enforced at API ingestion and storage layer; strict multi-tenancy.

<!-- GSD:project-end -->

<!-- GSD:stack-start source:STACK.md -->

## Technology Stack

Technology stack not yet documented. Will populate after codebase mapping or first phase.
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->

## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->

## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->

## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->

## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-fast` for a trivial task inline, with no subagents and no PLAN.md
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->

## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->