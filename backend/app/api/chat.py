from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agent.orchestrator import agent_orchestrator
from app.deps import get_current_user, require_role
from app.router.registry import global_registry

router = APIRouter()


class ChatRequest(BaseModel):
    prompt: str
    image_doc_id: Optional[str] = None
    user_approved: Optional[bool] = False
    expected_step_index: Optional[int] = 0


@router.post("/chat")
def chat_endpoint(req: ChatRequest, user: dict = Depends(get_current_user)):
    """
    user_id, user_role and data_scope come from the authenticated session, not
    the request body — a client can no longer grant itself a wider scope than
    its logged-in account actually has.
    """
    allowed_models = [m.id for m in global_registry.list_models()]
    return agent_orchestrator.process_request(
        prompt=req.prompt,
        user_id=user["user_id"],
        user_role=user["role"],
        data_scope=user["data_scopes"],
        allowed_models=allowed_models,
        image_doc_id=req.image_doc_id,
        user_approved=req.user_approved,
        expected_step_index=req.expected_step_index,
    )


@router.get("/models")
def list_models_endpoint():
    """Returns the dynamic model registry manifest list."""
    return {"models": [m.model_dump() for m in global_registry.list_models()]}


@router.post("/models/reload")
def reload_manifest_endpoint(user: dict = Depends(require_role("admin"))):
    """Hot-reloads models_manifest.yaml without restart."""
    global_registry.reload()
    return {"status": "reloaded", "count": len(global_registry.list_models())}
