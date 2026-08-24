import time
from typing import Any, Dict, List

from app.db import GENESIS_HASH, get_db, hash_row


class AuditLogger:
    """
    Durable, tamper-evident audit trail. Every event is appended to SQLite and
    chained to the previous row's hash (app.db.hash_row) — altering or deleting
    a past row breaks verify_audit_chain() for every row after it. Survives
    restarts, unlike the previous in-memory list that reset on every reload.
    """

    def log_event(self, user_id: str, action: str, risk_tier: str, outcome: str, details: str = "") -> Dict[str, Any]:
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        with get_db() as conn:
            row = conn.execute("SELECT MAX(seq) as m, row_hash FROM audit_log ORDER BY seq DESC LIMIT 1").fetchone()
            seq = (row["m"] or 0) + 1 if row and row["m"] is not None else 1
            prev_hash = row["row_hash"] if row and row["row_hash"] else GENESIS_HASH
            event_id = f"AUD-{seq:06d}"
            row_hash = hash_row(prev_hash, event_id, user_id, action, risk_tier, outcome, details, timestamp)

            conn.execute(
                "INSERT INTO audit_log (event_id, seq, user_id, action, risk_tier, outcome, details, timestamp, prev_hash, row_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (event_id, seq, user_id, action, risk_tier, outcome, details, timestamp, prev_hash, row_hash),
            )

        return {
            "event_id": event_id, "user_id": user_id, "action": action, "risk_tier": risk_tier,
            "outcome": outcome, "details": details, "timestamp": timestamp,
        }

    def get_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT event_id, user_id, action, risk_tier, outcome, details, timestamp "
                "FROM audit_log ORDER BY seq DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]


audit_logger = AuditLogger()
