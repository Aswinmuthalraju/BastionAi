import time
import uuid
from typing import Any, Dict, List, Optional

from app.db import get_db


class MemoryEntry:
    def __init__(
        self,
        entry_id: str,
        content: str,
        category: str = "action",  # action, conclusion, user_correction
        importance: float = 3.0,   # 1.0 to 5.0 scale
        task_id: Optional[str] = None,
        created_at: Optional[float] = None,
    ):
        self.entry_id = entry_id
        self.content = content
        self.category = category
        self.importance = max(1.0, min(5.0, importance))
        self.task_id = task_id or f"TASK-{uuid.uuid4().hex[:6].upper()}"
        self.created_at = created_at if created_at is not None else time.time()
        self.timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self.created_at))

    def recency_score(self) -> float:
        """Decays recency score based on elapsed age (half life ~ 1 hour)."""
        age_seconds = time.time() - self.created_at
        decay = 1.0 / (1.0 + (age_seconds / 3600.0))
        return round(decay, 3)

    def composite_score(self) -> float:
        return round(self.importance * 0.7 + self.recency_score() * 0.3, 2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "content": self.content,
            "category": self.category,
            "importance": self.importance,
            "recency_score": self.recency_score(),
            "composite_score": self.composite_score(),
            "task_id": self.task_id,
            "timestamp": self.timestamp_str,
        }


class AgentMemoryModule:
    """
    Agent working memory, backed by SQLite (app.db). `self.entries` remains an
    in-memory dict for the same interface callers already use, but every
    mutation is written through to disk so memory survives a restart — the
    previous version lost everything (including its seeded fake entries) on
    every reload.
    """

    def __init__(self):
        self.entries: Dict[str, MemoryEntry] = {}
        self._load_from_db()

    def _load_from_db(self):
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM memory_entries").fetchall()
        for r in rows:
            entry = MemoryEntry(r["entry_id"], r["content"], r["category"], r["importance"], r["task_id"], r["created_at"])
            self.entries[entry.entry_id] = entry

    def add_entry(self, content: str, category: str = "action", importance: float = 3.0, task_id: Optional[str] = None) -> MemoryEntry:
        entry_id = f"MEM-{uuid.uuid4().hex[:8].upper()}"
        entry = MemoryEntry(entry_id, content, category, importance, task_id)
        self.entries[entry_id] = entry
        with get_db() as conn:
            conn.execute(
                "INSERT INTO memory_entries (entry_id, content, category, importance, task_id, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (entry.entry_id, entry.content, entry.category, entry.importance, entry.task_id, entry.created_at),
            )
        return entry

    def purge_entry(self, entry_id: str) -> bool:
        if entry_id not in self.entries:
            return False
        del self.entries[entry_id]
        with get_db() as conn:
            conn.execute("DELETE FROM memory_entries WHERE entry_id = ?", (entry_id,))
        return True

    def consolidate_memory(self, threshold_score: float = 2.5) -> Dict[str, Any]:
        """Summarizes and prunes low-importance, low-recency entries; keeps high-importance ones intact."""
        initial_count = len(self.entries)
        purged_ids = []
        consolidated_summary = []

        for entry_id, entry in list(self.entries.items()):
            score = entry.composite_score()
            if score < threshold_score and entry.importance < 3.0:
                purged_ids.append(entry_id)
                consolidated_summary.append(f"[{entry.category.upper()}] {entry.content}")
                self.purge_entry(entry_id)

        summary_text = None
        if consolidated_summary:
            summary_text = f"Consolidated {len(consolidated_summary)} low-importance working memories: " + "; ".join(consolidated_summary)
            self.add_entry(summary_text, category="conclusion", importance=3.5)

        return {
            "initial_count": initial_count,
            "final_count": len(self.entries),
            "purged_count": len(purged_ids),
            "purged_ids": purged_ids,
            "consolidated_summary": summary_text,
        }

    def list_memories(self) -> List[Dict[str, Any]]:
        sorted_entries = sorted(self.entries.values(), key=lambda e: e.composite_score(), reverse=True)
        return [e.to_dict() for e in sorted_entries]


memory_module = AgentMemoryModule()
