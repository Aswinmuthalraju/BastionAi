from typing import Dict, Any, List
from app.passport.model import AutonomyTier

class RiskScorer:
    """
    Risk Scorer Engine.
    Evaluates Task Risk based on Data Sensitivity (1-5), Action Reversibility (1-5), and Tool Danger (1-5).
    Determines required Autonomy Tier for Task Passport.
    """
    
    TOOL_DANGER_MAP = {
        "rag_search": 1,
        "graph_query": 1,
        "pid_extractor": 2,
        "math_calculator": 1,
        "report_generator": 2,
        "valve_override": 5,
        "system_shutdown": 5,
        "shell_execution": 4,
        "database_purge": 5
    }

    DATA_SENSITIVITY_MAP = {
        "public": 1,
        "refinery_ops": 2,
        "PID-101": 3,
        "unreleased_design": 4,
        "confidential_negotiation": 5,
        "defence_classified": 5
    }

    def score_task(
        self,
        prompt: str,
        data_scope: str = "refinery_ops",
        requested_tools: List[str] = None
    ) -> Dict[str, Any]:
        prompt_lower = prompt.lower()
        requested_tools = requested_tools or ["rag_search"]

        # 1. Evaluate Data Sensitivity Score (1 to 5)
        sensitivity = self.DATA_SENSITIVITY_MAP.get(data_scope, 2)

        # 2. Evaluate Tool Danger Level (1 to 5)
        tool_danger = 1
        for tool in requested_tools:
            tool_danger = max(tool_danger, self.TOOL_DANGER_MAP.get(tool, 3))

        # 3. Evaluate Action Reversibility (1 to 5: 1=Read-only/Reversible, 5=Irreversible physical/financial)
        reversibility = 1
        risk_factors = []

        if any(w in prompt_lower for w in ["shut down", "shutdown", "close valve", "purge", "delete", "override"]):
            reversibility = 5
            risk_factors.append("Irreversible industrial physical command requested.")
        elif any(w in prompt_lower for w in ["negotiation", "contract", "financial", "purchase"]):
            reversibility = 4
            risk_factors.append("Confidential financial commitment action.")
        elif any(w in prompt_lower for w in ["modify", "update", "write"]):
            reversibility = 3
            risk_factors.append("State modification action.")
        else:
            risk_factors.append("Read-only informational query.")

        # Total Risk Score (scale 0.0 - 10.0)
        # Weighted formula: Sensitivity * 0.8 + ToolDanger * 0.9 + Reversibility * 1.2
        total_score = round(sensitivity * 0.8 + tool_danger * 0.9 + reversibility * 1.2, 1)

        # Map Total Score to Autonomy Tier
        if total_score < 3.5:
            autonomy_tier = AutonomyTier.AUTO_EXECUTE
        elif total_score < 5.5:
            autonomy_tier = AutonomyTier.EXECUTE_AND_VERIFY
        elif total_score < 8.0:
            autonomy_tier = AutonomyTier.HUMAN_APPROVAL_REQUIRED
        else:
            autonomy_tier = AutonomyTier.DUAL_APPROVAL_REQUIRED

        return {
            "total_risk_score": total_score,
            "autonomy_tier": autonomy_tier,
            "sensitivity": sensitivity,
            "tool_danger": tool_danger,
            "reversibility": reversibility,
            "risk_factors": risk_factors,
            "requires_human_pause": autonomy_tier in [AutonomyTier.HUMAN_APPROVAL_REQUIRED, AutonomyTier.DUAL_APPROVAL_REQUIRED]
        }

risk_scorer = RiskScorer()
