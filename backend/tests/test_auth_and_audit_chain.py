from app.audit.logger import audit_logger
from app.auth.providers import LocalAuthProvider
from app.auth.security import create_access_token, decode_access_token
from app.db import get_db, verify_audit_chain


def test_seeded_users_authenticate_with_real_argon2_hashes():
    provider = LocalAuthProvider()
    provider.seed_if_empty()

    user = provider.authenticate("operator", "Refinery-Ops-2026!")
    assert user is not None
    assert user["role"] == "operator"
    assert "PID-101" in user["data_scopes"]

    # Wrong password must fail — the old stub accepted any password at all.
    assert provider.authenticate("operator", "wrong-password") is None
    assert provider.authenticate("nonexistent-user", "anything") is None


def test_admin_scope_is_wildcard_not_client_supplied():
    provider = LocalAuthProvider()
    provider.seed_if_empty()
    admin = provider.authenticate("admin", "Sovereign-Audit-2026!")
    assert admin["data_scopes"] == ["*"]


def test_jwt_roundtrip_and_tamper_rejection():
    token = create_access_token("user-abc123", "operator", "operator")
    payload = decode_access_token(token)
    assert payload["sub"] == "user-abc123"
    assert payload["role"] == "operator"

    tampered = token[:-4] + "abcd"
    try:
        decode_access_token(tampered)
        assert False, "tampered token must not decode"
    except Exception:
        pass


def test_audit_hash_chain_detects_tampering():
    audit_logger.log_event("test-user", "TEST_ACTION_A", "auto_execute", "SUCCESS", "first")
    audit_logger.log_event("test-user", "TEST_ACTION_B", "auto_execute", "SUCCESS", "second")

    result = verify_audit_chain()
    assert result["valid"] is True

    # Directly corrupt a row's content without updating its hash — simulating tampering.
    with get_db() as conn:
        row = conn.execute("SELECT event_id FROM audit_log ORDER BY seq ASC LIMIT 1").fetchone()
        conn.execute("UPDATE audit_log SET details = ? WHERE event_id = ?", ("TAMPERED", row["event_id"]))

    result_after = verify_audit_chain()
    assert result_after["valid"] is False
