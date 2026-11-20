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

Read the actual SaaS fleet using the generated operator credential. Keep the credential in the local process and out of reports.

    $operator = Get-Content -Raw .cicada/dev/operator-alpha.json | ConvertFrom-Json
    curl.exe --cacert .cicada/dev/ca.pem -H "Authorization: Bearer $($operator.token)" -H "X-Tenant-ID: $($operator.tenant_id)" https://localhost:8443/api/v1/fleet

Open http://localhost:9001/audit separately. Enter the local_token value from .cicada/dev/collector-alpha.json to inspect the input preview, the exact approved outbound bytes, and the SaaS receipt. The local session token and operator token have distinct scopes.

## Schema and dashboard handoff

    .venv/Scripts/python -m scripts.security.export_contracts

Share the generated OpenAPI and synthetic metadata, heartbeat, and receipt examples under .cicada/contracts. They contain no live credentials. Frontend dev CORS accepts only the configured localhost origin. SaaS can serve a React build using --dashboard frontend/dist from the integration checkout. For a direct HTTPS browser run, trust only the locally generated development CA in the browser's trust store after inspecting its source.

The dashboard branch at 1d90f88 defaults to a fixed development tenant and token and still displays a verified-gates footer. Its integration follow-up is operator-supplied credentials and evidence-backed status. The browser check supplies fresh credentials to the real tenant-scoped API through a CA-verified HTTPS client. Keep the application credentials generated per runtime.

## Verification

    .venv/Scripts/python -m pytest -q

Phase 1 tests exercise actual collector and SaaS processes with temporary certificates and databases. Set CICADA_TEST_DASHBOARD to a built dashboard directory to also verify the receipt renders in a browser. Set CICADA_TEST_BROWSER to msedge or use a Playwright-installed Chromium.

V00 still needs an actual organizer sample. V02 covers the implemented collector/operator routes. Action and subscription checks apply once those capabilities exist. Phase 1 sends directly and reports delivery errors. The durable outbox is Phase 3, full health is Phase 4, and local auth aggregation is Phase 5.
