# Phase 6: Autonomous Ops Simulator & Policy-Guarded Remediation — Research

**Researched:** 2026-11-20
**Domain:** Assisted Operations, Policy-as-Code Safety Gates, Human-in-the-Loop Approval, Reversible Actions, Audit Trails
**Confidence:** HIGH

<user_constraints>
## User Constraints (from Hackathon Guide & PROJECT.md)

### Locked Decisions
- 24-Hour Hackathon Scope: Automated actions must be simulated or restricted to a safe test environment (no destructive live infrastructure commands).
- Policy-Controlled: Every proposed remediation action must be verified against safety policies (e.g. rate limits, prohibited commands, maintenance windows).
- Human-in-the-Loop Gate: Actions require explicit human operator review and confirmation ("Approve Action") before simulated execution.
- Immutable Audit Trail: Every proposed, approved, executed, and rolled-back action must be recorded with UTC timestamps, operator ID, and state deltas.
- Rollback Plan: Every executable action must have an automated, verified compensatory rollback definition.

### Claude's Discretion
- Simulation Sandbox: Python stateful simulation runner maintaining virtual service/node states (e.g., `service_status: RESTARTED`, `memory_pool: EXPANDED`, `ip_blocked: TRUE`).
- Policy Rules: Declarative JSON/YAML policy definitions (e.g., `max_actions_per_hour: 5`, `require_human_confirmation: true`).
</user_constraints>

<architectural_responsibility_map>
## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
| :--- | :--- | :--- | :--- |
| Remediation Proposal Generator | Tier 2 (Central SaaS) | — | Matches incident root causes to pre-approved operational playbooks |
| Policy-as-Code Gate | Tier 2 (Central SaaS) | — | Evaluates proposed action safety, checks rate limits and constraints |
| Human Approval Workflow | Tier 2 (Central SaaS) | Dashboard Tier | Interactive UI modal presenting action details, risk tier, and approve/reject controls |
| Remediation Simulator & Rollback Engine | Tier 2 (Central SaaS) | Tier 1 (Customer Edge) | Simulates action execution, logs audit records, and executes rollback on operator command |
| </architectural_responsibility_map>

<research_summary>
## Summary

Phase 6 implements the transition from Assisted Operations to Autonomous Operations, fulfilling the Phase 5 roadmap milestone and Live Scenario 8 of the evaluation guide:
1. **Playbook Matching Engine**:
   - For an incident (e.g., `CPU exhaustion on auth-service`), the recommender generates an actionable remediation payload:
     - `action_type`: `RESTART_SERVICE` / `SCALE_CONTAINER_MEMORY` / `BLOCK_MALICIOUS_IP`
     - `target_component`: `auth-worker-02`
     - `risk_level`: `LOW` / `MEDIUM`
     - `compensatory_rollback`: `ROLLBACK_SERVICE_STATE`
2. **Policy Safety Gate**:
   - Checks against `remediation_policy.json`:
     - Disallows unapproved destructive actions (e.g., `DROP_TABLE`, `REBOOT_SYSTEM`).
     - Enforces mandatory human approval for all state mutations.
3. **Execution Simulator & Audit Ledger**:
   - When the operator clicks "Approve & Execute", the simulator applies the state change in the virtual environment.
   - Logs an audit entry: `{action_id, timestamp_utc, operator_id, policy_verdict: "APPROVED", status: "SIMULATED_SUCCESS", rollback_prepared: true}`.
   - The UI displays a "Rollback Action" button which restores prior state and logs the compensation.
</research_summary>

## Key Implementation Patterns
- Command pattern with paired execute() and rollback() handlers.
- Immutable append-only audit ledger.
- Safe sandbox environment showing immediate simulated metric recovery.
