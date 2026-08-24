from typing import Any, Dict

from fastapi import APIRouter, Body, Depends

from app.audit.logger import audit_logger
from app.db import verify_audit_chain
from app.deps import require_role
from app.router.registry import ModelManifestItem, global_registry
from app.security.quarantine import quarantine_manager

router = APIRouter()


@router.get("/admin/audit-logs")
def get_audit_logs(user: dict = Depends(require_role("admin"))):
    return {"logs": audit_logger.get_logs()}


@router.get("/admin/audit-logs/verify")
def verify_audit_logs(user: dict = Depends(require_role("admin"))):
    """Recomputes the audit hash chain end-to-end to prove the trail hasn't been tampered with."""
    return verify_audit_chain()


@router.get("/admin/quarantine-alerts")
def get_quarantine_alerts(user: dict = Depends(require_role("admin"))):
    return {"alerts": quarantine_manager.get_all()}


@router.post("/admin/models/add")
def add_model_dynamic(item: Dict[str, Any] = Body(...), user: dict = Depends(require_role("admin"))):
    """Dynamically register a new model entry into the running registry."""
    model_item = ModelManifestItem(**item)
    global_registry.add_model(model_item)
    return {"status": "added", "model": model_item.model_dump()}
