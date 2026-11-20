# Team working agreement

Read PROJECT_OVERVIEW.md and .planning/TEAM_EXECUTION.md before work. This repository currently contains plans only; implement application code only when the user requests the build.

Use the assigned member guide, owned paths and feature branch. M1 owns shared contracts, security, persistence, backend analytics and integration. M2 owns frontend. M3 owns adapters, pure demo source, local HTML, scenario fixtures/verification and runbook. Ask the lead to resolve interface conflicts rather than independently changing contracts. Do not spawn extra agents unless explicitly requested by the user.

.planning/CONTRACTS.md is the interface authority; REQUIREMENTS.md is the ID authority. Follow GIT_WORKFLOW.md and VALIDATION.md. No unavailable model-specific slash command is required. Keep work small, run relevant checks, update only your own status file, and report evidence honestly.

Never send raw collector data to SaaS, fake scenario results, silently substitute mocks, disable TLS verification or overwrite another member's work. No secrets/runtime databases in Git, no force-push, no automatic deployment. Planning commands describe future execution, not completed results.
