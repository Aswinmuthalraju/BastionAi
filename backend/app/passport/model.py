from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum
import time
import uuid

class AutonomyTier(str, Enum):
    AUTO_EXECUTE = "auto_execute"
    EXECUTE_AND_VERIFY = "execute_and_verify"
    HUMAN_APPROVAL_REQUIRED = "human_approval_required"
    DUAL_APPROVAL_REQUIRED = "dual_approval_required"

class TaskPassport(BaseModel):
    task_id: str = Field(default_factory=lambda: f"TASK-{uuid.uuid4().hex[:8].upper()}")
    user_id: str = "eng-user-01"
    user_role: str = "operator"
    data_scope: List[str] = Field(default_factory=lambda: ["public", "refinery_ops", "PID-101"])
    allowed_models: List[str] = Field(default_factory=lambda: ["llama-3.3-70b", "qwen2.5-coder", "qwen2-vl"])
    allowed_tools: List[str] = Field(default_factory=lambda: ["rag_search", "graph_query", "pid_extractor", "math_calculator"])
    autonomy_required: AutonomyTier = AutonomyTier.AUTO_EXECUTE
    risk_score: float = 0.0
    risk_factors: List[str] = Field(default_factory=list)
    created_at: float = Field(default_factory=time.time)

    def validate_access(self, doc_scope: str) -> bool:
        """Check if requested document scope is allowed under this passport."""
        if "*" in self.data_scope:
            return True
        return doc_scope in self.data_scope

    def validate_model(self, model_id: str) -> bool:
        """Check if model is permitted under this passport."""
        return model_id in self.allowed_models

    def validate_tool(self, tool_name: str) -> bool:
        """Check if tool execution is permitted under this passport."""
        return tool_name in self.allowed_tools
