# Run Phase 1

These commands use PowerShell from the repository root and keep runtime files in the ignored .cicada directory.

    python -m venv .venv
    .venv/Scripts/python -m pip install -r requirements.lock
    .venv/Scripts/python -m scripts.security.bootstrap

Bootstrap creates alpha and beta collector/operator credentials and a short-lived certificate for localhost and 127.0.0.1. Use a private local workspace. Reuse the runtime to retain source pseudonyms across restarts. Use a new directory to regenerate the CA and credentials together.

Start SaaS in one terminal.

    .venv/Scripts/python -m backend.saas.main

Start the collector in another terminal.

    .venv/Scripts/python -m backend.collector.daemon

The collector labels its synthetic input DEMO_FALLBACK and reports approved metrics over verified HTTPS. Use --tenant beta in a third terminal for the second tenant. Use --once for a single batch and exit, --input for local RawEvent JSONL, or --organizer for an organizer-format JSONL replay. An explicitly missing or malformed input is a failed run. Organizer input sources must be configured on both tiers before ingest.

The collector stores approved bodies in a SQLite outbox under the runtime directory. Keep that directory when restarting a collector. Run one collector per configured identity. The default capacity is 1,000 records and can be set with `outbox_capacity` in the collector JSON. An outage pauses inputs at capacity, without evicting committed records. Quarantined records also occupy capacity and are visible through the authenticated local status endpoint. `--once` allows 20 seconds for input and delivery, then exits unsuccessfully if it times out or quarantine remains. Committed records remain available for the next restart.

To demonstrate recovery, stop SaaS for 30 seconds with the collector running, then restart SaaS with the same runtime. Use `/api/local/status` to observe queue depth and receipt counts. Verify delivery against central payload UUIDs. The automated integration test checks the exact UUID and body sets across a collector restart.

Read the actual SaaS fleet using the generated operator credential. Keep the credential in the local process and out of reports.

    $operator = Get-Content -Raw .cicada/dev/operator-alpha.json | ConvertFrom-Json
    curl.exe --cacert .cicada/dev/ca.pem -H "Authorization: Bearer $($operator.token)" -H "X-Tenant-ID: $($operator.tenant_id)" https://localhost:8443/api/v1/fleet

Open http://localhost:9001/audit separately. Enter the local_token value from .cicada/dev/collector-alpha.json to inspect the masked local preview, the exact approved outbound bytes, and the SaaS receipt. Paste an optional UUID to retrieve a specific retained record. The local session token and operator token have distinct scopes.

## Schema and dashboard handoff

    .venv/Scripts/python -m scripts.security.export_contracts

Share the generated OpenAPI and synthetic metadata, heartbeat, and receipt examples under .cicada/contracts. They contain no live credentials. Frontend dev CORS accepts only the configured localhost origin. SaaS can serve a React build using --dashboard frontend/dist from the integration checkout. For a direct HTTPS browser run, trust only the locally generated development CA in the browser's trust store after inspecting its source.

Build with npm --prefix frontend ci and npm --prefix frontend run build. Start SaaS with --dashboard frontend/dist. In the dashboard enter the tenant ID and token from .cicada/dev/operator-alpha.json and connect. Look up the UUID from the local window, then paste the local SHA-256 digest. Matching digests show agreement for the selected request body. The privacy checks separately inspect SaaS data for forbidden fields and secret markers.

For the privacy demo, start the alpha collector with --input tests/scenarios/fixtures/secrets.jsonl. Keep it running to inspect the retained records. The fixture timestamps are historical and are unsuitable for live latency claims.

## Verification

Phase 5 dependency correlation uses the graph in `saas.json`. Bootstrap a new runtime directory for the demo if your existing runtime was created before this graph was added. Run the SaaS and collector with the same `--runtime` path. Confirm incident behavior against the live test with `.venv/Scripts/python -m pytest -q -s tests/core/test_phase5.py`. These checks use synthetic input and temporary credentials.

    .venv/Scripts/python -m pytest -q

Phase 1 tests exercise actual collector and SaaS processes with temporary certificates and databases. Set CICADA_TEST_DASHBOARD to a built dashboard directory to also verify the receipt renders in a browser. Set CICADA_TEST_BROWSER to msedge or use a Playwright-installed Chromium.

V00 still needs an actual organizer sample. V02 covers the implemented collector/operator routes. Action and subscription checks apply once those capabilities exist.
