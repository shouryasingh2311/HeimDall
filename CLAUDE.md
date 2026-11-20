# HeimDall - Project Instructions

Privacy-first distributed observability and AIOps platform ready for production deployment across edge, datacenters, IoT, and cloud infrastructure.

## Tech Stack
- **Backend**: Python 3.11+, FastAPI, Uvicorn, aiosqlite, cryptography, Pydantic v2, HTTPX.
- **Frontend**: React 19, TypeScript, Vite, pure CSS (high-contrast dark mode), native SVG sparklines.
- **Database / Storage**: SQLite with WAL mode, local outbox buffering, SHA-256 deduplication.
- **Security / Wire**: TLS with verified CA, HMAC pseudonyms, zero-raw-log egress.

## Build & Run
- **Remote 1-Liner (Zero-Git)**:
  - Windows: `irm https://raw.githubusercontent.com/shouryasingh2311/HeimDall/main/install.ps1 | iex`
  - Linux/macOS: `curl -fsSL https://raw.githubusercontent.com/shouryasingh2311/HeimDall/main/install.sh | bash`
- **1-Click Windows**: Double-click `run.bat` (auto-bootstraps and opens browser)
- **1-Command Docker**: `docker compose up` (builds frontend, installs python deps, bootstraps certs & tokens, starts both services)
- **1-Command Native**: `.\start.ps1` (Windows) or `./start.sh` (Linux/macOS)
- **Manual Bootstrap**: `.venv/Scripts/python -m scripts.security.bootstrap --runtime .heimdal/demo`
- **Manual SaaS**: `.venv/Scripts/python -m backend.saas.main --runtime .heimdal/demo --dashboard frontend/dist`
- **Manual Collector**: `.venv/Scripts/python -m backend.collector.daemon --runtime .heimdal/demo --scenarios`
- **Frontend Dev**: `cd frontend && npm run dev`
- **Frontend Build**: `cd frontend && npm run build`
- **Frontend Lint**: `cd frontend && npm run lint`

## Testing
- **UI Verification Suite**: `node tests/ui/test-client.mjs` (15/15 Phase 1-8 checks)
- **Backend Unit & Scenario Tests**: `pytest` or `pytest -p no:asyncio tests/scenarios`
- **Live Scenario Verification**: `python scripts/verification/run_scenarios.py`

## Project Structure
- `backend/collector/`: Customer-local collector daemon, outbox queue, local regex sanitizer, HMAC pseudonymizer, loopback proof/scenario server (port 9001).
- `backend/saas/`: Central SaaS ingest, rolling statistical baseline detector, incident correlation engine, remediation simulation & rollback (port 8443).
- `backend/shared/`: Shared Pydantic contracts, configuration schemas, crypto/digest utilities.
- `frontend/`: React 19 dashboard (Fleet status, Payload Inspector, Metrics SVG sparklines, Incident Correlation, Remediation controls, Scenario Results).
- `tests/`: `tests/core/` (backend regression), `tests/scenarios/` (black-box verification), `tests/ui/` (client-side checks).
- `docs/`: RUNBOOK.md (operations and live scenario verification runbook), API.md, ARCHITECTURE.md, CONTRACTS.md (schema authority).

## Core Conventions & Invariants
- **Two-Tier Privacy Rule**: Customer local logs/secrets NEVER leave localhost (`http://localhost:9001/audit`). SaaS only receives allowlisted metadata and SHA-256 wire body digests.
- **Lean Dependencies (Ponytail)**: Prefer stdlib and native platform features. No heavy charting libraries (pure SVG sparklines). No unrequested abstractions.
- **Contract Authority**: `docs/CONTRACTS.md` is the canonical schema authority. Do not alter backend contracts without coordination.
- **Error Handling**: Fail honestly on 503/network errors; zero mock fallback during live connectivity.
- **Git & Commits**: Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`) with small, scoped diffs.
