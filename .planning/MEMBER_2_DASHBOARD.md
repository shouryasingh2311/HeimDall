# Member 2 — dashboard using the user's Gemini Flash setup

Branch feat/operations-dashboard. Own frontend/**, tests/ui/** and status/MEMBER_2.md. Read PROJECT_OVERVIEW.md, CONTRACTS.md, TEAM_EXECUTION.md and GIT_WORKFLOW.md. Work in small tasks with explicit expected JSON; do not redesign backend/security.

## Execution queue across all eight phases

1. Phase 1 / G0-G1: scaffold React/TypeScript/Vite, commit package lockfile, one typed API wrapper and basic connection/error states. Use lead-approved metadata fixtures only, permanently labelled MOCK until live wiring.
2. Phase 2: build received-payload inspector (ID, approved fields, digest, receipt time). Explain opening the separate local proof window. Never fetch, embed, proxy or store local raw records in this UI.
3. Phase 3: display queue depth/receipt/replay indicators supplied by API. Do not infer delivery success from an empty queue alone; display verified result counts.
4. Phase 4: fleet/source cards, four health states/reasons, last heartbeat, collector version/resources/config state, metric trends sorted by event time and UTC transition history. Implement first-visible-render receipt once per payload/session/run; no fetch-time shortcut.
5. Phase 5: incident list/detail, affected pseudonymous sources, observed/baseline values, contributing payload links, reasoning and 'heuristic evidence score' label. Do not display calibrated confidence or certain root cause.
6. Phase 6: proposal/approve/rollback UI from actual lifecycle. Show simulation label, pending collector result, failure and rollback state. Disable impossible actions in UI, but rely on backend authorization. Never set success locally on click.
7. Phase 7: show safe observed scenario results for all eight scenarios. Controls live on local runner; provide instructions/link to its separate page. No remote bridge to local raw endpoints. If API summary is blocked/failed, show it as such.
8. Phase 8: complete live dashboard, keyboard/accessibility basics, resize, polling failure/recovery, tenant cache reset and final build. No mock fallback during demo.

## Task method

Give the agent ONE component or client behavior at a time. Include CONTRACTS.md response shape and two examples (normal/error). Ask it to modify only owned files, preserve names and return changed files/check output. If a field is missing, record request in status file; do not invent an endpoint.

Suggested task sizes: API wrapper -> FleetHealth -> trend/history -> PayloadReceipt -> IncidentDetail -> RemediationControls -> ScenarioResults -> render timing. Use plain CSS/SVG rather than adding a UI framework late.

## Checks and handoff

Run npm ci after lockfile merge and npm run build before each UI PR. Add focused checks for first-render dedup, honest failure state and cache clearing; do not snapshot every CSS detail. At G1 show one real record; at G3 show actual backend incident; at G4 approve/rollback genuine simulated action; at G5 provide browser timing evidence. Update status/MEMBER_2.md every 30-45 min and push small commits.

## Agent task template

Implement [component] using the exact contract and metadata-only fixture. Touch frontend/[paths] only. Do not change auth, API names, schema, backend or local raw-data access. Show loading, empty, error and live states. Run the build without masking errors. Report assumptions and any missing API field.
