from types import SimpleNamespace

import backend.collector.inspector as inspector
from backend.collector.scrubber import scrub_preview


def test_masks_known_secrets_and_keeps_diagnostic_context():
    raw = (
        'timeout password="private pass" API_KEY=fixture-key Authorization: Bearer fixture-token '
        'postgres://operator:fixture-pass@localhost/db\n'
        '-----BEGIN PRIVATE KEY-----\nfixture-key-material\n-----END PRIVATE KEY-----'
    )
    preview = scrub_preview(raw)
    assert preview.startswith("timeout")
    assert "localhost/db" in preview
    assert "[REDACTED]" in preview
    for secret in ("private pass", "fixture-key", "fixture-token", "fixture-pass", "operator:"):
        assert secret not in preview


def test_audit_count_and_age_limits_apply_to_uuid_lookup(monkeypatch):
    now = 0
    monkeypatch.setattr(inspector, "monotonic", lambda: now)
    audit = inspector.AuditPreview(max_records=2, ttl_seconds=5)
    for identifier in ("discarded", "expires"):
        audit.add(SimpleNamespace(raw_text="password=fixture"), SimpleNamespace(
            payload_uuid=identifier, policy_version="metadata-v1",
        ), b"{}")
    now = 4
    audit.add(SimpleNamespace(raw_text=None), SimpleNamespace(
        payload_uuid="retained", policy_version="metadata-v1",
    ), b"{}")
    assert audit.by_id("discarded") is None
    assert audit.by_id("expires")["raw_preview"] == "password=[REDACTED]"
    now = 5
    assert audit.by_id("expires") is None
    assert [record["payload_uuid"] for record in audit.latest()] == ["retained"]
