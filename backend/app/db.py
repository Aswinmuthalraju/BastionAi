import hashlib
import sqlite3
import time
from contextlib import contextmanager

from app import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL,
    department TEXT NOT NULL,
    data_scopes TEXT NOT NULL,   -- JSON array
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    event_id TEXT PRIMARY KEY,
    seq INTEGER,
    user_id TEXT NOT NULL,
    action TEXT NOT NULL,
    risk_tier TEXT NOT NULL,
    outcome TEXT NOT NULL,
    details TEXT,
    timestamp TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quarantine (
    item_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    source TEXT NOT NULL,
    page INTEGER NOT NULL,
    trace TEXT NOT NULL,
    quarantined_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS memory_entries (
    entry_id TEXT PRIMARY KEY,
    content TEXT NOT NULL,
    category TEXT NOT NULL,
    importance REAL NOT NULL,
    task_id TEXT,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT PRIMARY KEY,
    filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    content_type TEXT NOT NULL,
    data_scope TEXT NOT NULL,
    allowed_roles TEXT NOT NULL, -- JSON array
    page_count INTEGER NOT NULL,
    status TEXT NOT NULL,        -- ingesting | indexed | quarantined | failed
    uploaded_by TEXT NOT NULL,
    uploaded_at REAL NOT NULL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS equipment_state (
    equipment_id TEXT PRIMARY KEY,
    state TEXT NOT NULL,
    last_changed_by TEXT,
    last_changed_at REAL
);
"""

GENESIS_HASH = "0" * 64


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(config.SQLITE_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def get_db():
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_db() as conn:
        conn.executescript(SCHEMA)


def hash_row(prev_hash: str, *fields: str) -> str:
    """Chains each audit row to the previous one so tampering with history is detectable."""
    payload = prev_hash + "|" + "|".join(fields)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def verify_audit_chain() -> dict:
    """Recomputes the hash chain over the full audit log and reports the first break, if any."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT event_id, seq, user_id, action, risk_tier, outcome, details, timestamp, prev_hash, row_hash "
            "FROM audit_log ORDER BY seq ASC"
        ).fetchall()

    expected_prev = GENESIS_HASH
    for row in rows:
        if row["prev_hash"] != expected_prev:
            return {"valid": False, "broken_at": row["event_id"], "reason": "prev_hash mismatch"}
        recomputed = hash_row(
            row["prev_hash"], row["event_id"], row["user_id"], row["action"],
            row["risk_tier"], row["outcome"], row["details"] or "", row["timestamp"],
        )
        if recomputed != row["row_hash"]:
            return {"valid": False, "broken_at": row["event_id"], "reason": "row_hash mismatch — content altered"}
        expected_prev = row["row_hash"]

    return {"valid": True, "checked_rows": len(rows)}
