import json
import time
import uuid
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from app import config
from app.auth.security import hash_password, verify_password
from app.db import get_db

# Dev-only seed accounts. Passwords are real Argon2id hashes (not plaintext, not
# a bypass) but the plaintext values below are published in SETUP.md as the
# known first-run credentials — rotate them before any real deployment.
SEED_USERS = [
    {
        "username": "operator", "password": "Refinery-Ops-2026!",
        "full_name": "Vikram Sharma", "role": "operator",
        "department": "Refinery Operations & Maintenance",
        "data_scopes": ["public", "refinery_ops", "PID-101"],
    },
    {
        "username": "engineer", "password": "Process-Auto-2026!",
        "full_name": "Ananya Roy", "role": "engineer",
        "department": "Process Automation & Instrumentation",
        "data_scopes": ["public", "refinery_ops", "PID-101", "unreleased_design"],
    },
    {
        "username": "admin", "password": "Sovereign-Audit-2026!",
        "full_name": "Col. R. K. Verma", "role": "admin",
        "department": "Sovereign Defence & Infrastructure Security",
        "data_scopes": ["*"],
    },
]


class AuthProvider(ABC):
    @abstractmethod
    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Returns a user record dict on success, or None on invalid credentials."""


class LocalAuthProvider(AuthProvider):
    """Argon2id password hashing against the local SQLite user store. Default provider for this environment."""

    def seed_if_empty(self):
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) as c FROM users").fetchone()["c"]
            if count > 0:
                return
            for u in SEED_USERS:
                conn.execute(
                    "INSERT INTO users (user_id, username, password_hash, full_name, role, department, data_scopes, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"user-{uuid.uuid4().hex[:8]}", u["username"], hash_password(u["password"]),
                        u["full_name"], u["role"], u["department"], json.dumps(u["data_scopes"]), time.time(),
                    ),
                )

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE username = ?", (username.lower(),)).fetchone()
        if row is None or not verify_password(password, row["password_hash"]):
            return None
        return {
            "user_id": row["user_id"], "username": row["username"], "full_name": row["full_name"],
            "role": row["role"], "department": row["department"], "data_scopes": json.loads(row["data_scopes"]),
        }

    def get_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()
        if row is None:
            return None
        return {
            "user_id": row["user_id"], "username": row["username"], "full_name": row["full_name"],
            "role": row["role"], "department": row["department"], "data_scopes": json.loads(row["data_scopes"]),
        }


class LDAPAuthProvider(AuthProvider):
    """
    Real LDAP bind via ldap3 — not wired up by default because no LDAP server is
    reachable in this environment. Activate with BASTION_AUTH_PROVIDER=ldap,
    BASTION_LDAP_SERVER_URI, BASTION_LDAP_BASE_DN. See SETUP.md.
    """

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        import ldap3

        if not config.LDAP_SERVER_URI:
            raise RuntimeError("BASTION_AUTH_PROVIDER=ldap requires BASTION_LDAP_SERVER_URI to be set.")

        server = ldap3.Server(config.LDAP_SERVER_URI, get_info=ldap3.ALL)
        user_dn = f"uid={username},{config.LDAP_BASE_DN}"
        try:
            conn = ldap3.Connection(server, user=user_dn, password=password, auto_bind=True)
        except ldap3.core.exceptions.LDAPBindError:
            return None

        conn.search(config.LDAP_BASE_DN, f"(uid={username})", attributes=["cn", "departmentNumber", "employeeType"])
        if not conn.entries:
            conn.unbind()
            return None

        entry = conn.entries[0]
        role = str(entry.employeeType) if "employeeType" in entry else "operator"
        conn.unbind()
        return {
            "user_id": f"ldap-{username}", "username": username,
            "full_name": str(entry.cn) if "cn" in entry else username,
            "role": role, "department": str(entry.departmentNumber) if "departmentNumber" in entry else "",
            "data_scopes": ["public", "refinery_ops"],
        }


def get_auth_provider() -> AuthProvider:
    if config.AUTH_PROVIDER == "ldap":
        return LDAPAuthProvider()
    return LocalAuthProvider()
