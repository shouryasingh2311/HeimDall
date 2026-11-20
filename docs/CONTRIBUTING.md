# Contributing & Development Guide

This guide details working agreements, branch policies, code quality standards, and testing procedures for team members and automated AI collaborators working on **Cicada**.

---

## 1. Team Ownership & Branch Strategy

Development proceeds across three bounded member workstreams to prevent merge collisions:

| Role | Branch | Owned Directory Paths | Primary Responsibility |
|---|---|---|---|
| **M1: Lead / Core** | `feat/core-platform` | `backend/shared/**`, `backend/saas/**`, `backend/collector/**` (excl. adapters/demo), `pyproject.toml`, `scripts/security/**`, `tests/core/**`, `.planning/CONTRACTS.md`, `.planning/STATE.md` | Core architecture, security sanitizer, SQLite outbox, SaaS APIs, AIOps engine, and integration. |
| **M2: Operations Dashboard** | `feat/operations-dashboard` | `frontend/**`, `tests/ui/**`, `.planning/status/MEMBER_2.md` | React 18 / Vite UI, fleet views, egress receipt inspector, render timing instrumentation. |
| **M3: Validation & Adapters** | `feat/fixtures-validation` | `backend/collector/adapters/**`, `backend/collector/demo_source.py`, `backend/collector/static/**`, `tests/scenarios/**`, `scripts/verification/**`, `docs/RUNBOOK.md`, `.planning/status/MEMBER_3.md` | Organizer stream adapter, local proof HTML, pure simulation source, 8-scenario verifiers. |

### Branch Rules
* Work only on your designated feature branch.
* Never push directly to `main`.
* M1 performs integration merges after each capability gate review.
* Do not edit files outside your assigned ownership path without explicit handoff.

---

## 2. Core Working Principles

1. **Never Send Raw Data to SaaS:** Never bridge raw logs, secrets, or passwords to the SaaS platform. Local proof is displayed on the collector's loopback interface only (`127.0.0.1:9001`).
2. **Never Disable TLS Verification:** `verify=False` is strictly forbidden in HTTP client calls. Use generated development CA certificates.
3. **No Fake Scenario Passes:** Test verifiers must evaluate actual database states, HTTP receipts, and network outcomes—never mock return values.
4. **Strict Schema Discipline:** All Pydantic models must use `extra="forbid"`. Do not pass arbitrary free-form dictionaries across network boundaries.
5. **Durable Persistence:** Every collector event must be committed to the SQLite outbox (`PRAGMA synchronous = FULL`) before transmission.

---

## 3. Development Workflow & Testing

### Running Tests Locally
Before requesting review or merging, ensure all tests pass:

```bash
# 1. Core backend and security tests
python -m pytest tests/core

# 2. 8 Hackathon scenario verifiers
python -m pytest tests/scenarios

# 3. Frontend TypeScript check and production build
cd frontend
npm run build
cd ..
```

### Pre-Commit Checklist
- [ ] No secrets, keys, or credentials committed.
- [ ] No temporary SQLite databases committed (`*.db`, `*.sqlite`, `*.wal`).
- [ ] Code formatted with Black/Ruff (`python -m ruff check .`).
- [ ] Frontend clean build without TypeScript errors.
- [ ] Member status file updated in `.planning/status/`.

---

## 4. Status Tracking

Every 30–45 minutes of active development:
* Update your personal status file:
  * Member 1: `.planning/status/MEMBER_1.md`
  * Member 2: `.planning/status/MEMBER_2.md`
  * Member 3: `.planning/status/MEMBER_3.md`
* Record:
  * Latest commit SHA.
  * Completed requirements / task IDs.
  * Checks executed with observed evidence.
  * Blockers or required interface updates.
