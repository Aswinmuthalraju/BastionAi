from typing import Any, Dict

from fastapi import APIRouter, Body, Depends, HTTPException

from app.deps import require_role
from app.mnemoshield.drift_detector import drift_detector
from app.mnemoshield.dual_rail_security import dual_rail_security
from app.mnemoshield.memory_module import memory_module

router = APIRouter()


@router.get("/mnemoshield/memory")
def get_working_memories(user: dict = Depends(require_role("admin"))):
    return {"memories": memory_module.list_memories()}


@router.delete("/mnemoshield/memory/{entry_id}")
def purge_working_memory(entry_id: str, user: dict = Depends(require_role("admin"))):
    success = memory_module.purge_entry(entry_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Memory entry {entry_id} not found.")
    return {"status": "purged", "entry_id": entry_id}


@router.post("/mnemoshield/memory/consolidate")
def consolidate_working_memory(threshold: float = 2.5, user: dict = Depends(require_role("admin"))):
    return memory_module.consolidate_memory(threshold_score=threshold)


@router.post("/mnemoshield/drift/eval")
def evaluate_trajectory_drift(payload: Dict[str, Any] = Body(...), user: dict = Depends(require_role("admin"))):
    action = payload.get("action", "")
    step_idx = payload.get("step_index", 0)
    return drift_detector.evaluate_action_drift(proposed_action=action, expected_step_index=step_idx)


@router.post("/mnemoshield/security/scan")
def scan_dual_rail_security(payload: Dict[str, Any] = Body(...), user: dict = Depends(require_role("admin"))):
    text = payload.get("text", "")
    source = payload.get("source", "User_Input_Prompt.pdf")
    page = payload.get("page", 1)
    return dual_rail_security.scan_content(text=text, source_filename=source, page_number=page)
