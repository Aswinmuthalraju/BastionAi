import time
from typing import Any, Dict, List

from app.db import get_db


class QuarantineManager:
    """Durable quarantine vault — persisted to SQLite so blocked items survive a restart."""

    def quarantine(self, content: str, source: str, page: int, trace: str) -> Dict[str, Any]:
        quarantined_at = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        with get_db() as conn:
            count = conn.execute("SELECT COUNT(*) as c FROM quarantine").fetchone()["c"]
            item_id = f"QRN-{count + 1:04d}"
            conn.execute(
                "INSERT INTO quarantine (item_id, content, source, page, trace, quarantined_at) VALUES (?, ?, ?, ?, ?, ?)",
                (item_id, content, source, page, trace, quarantined_at),
            )
        return {"item_id": item_id, "content": content, "source": source, "page": page, "trace": trace, "quarantined_at": quarantined_at}

    def get_all(self) -> List[Dict[str, Any]]:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM quarantine ORDER BY quarantined_at DESC").fetchall()
        return [
            {
                "item_id": r["item_id"],
                "content_snippet": r["content"][:100] + ("..." if len(r["content"]) > 100 else ""),
                "source": r["source"],
                "page": r["page"],
                "trace": r["trace"],
                "quarantined_at": r["quarantined_at"],
            }
            for r in rows
        ]


quarantine_manager = QuarantineManager()
