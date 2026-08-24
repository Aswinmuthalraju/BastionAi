from app.agent.risk_scorer import risk_scorer
from app.passport.model import AutonomyTier
from app.agent.orchestrator import agent_orchestrator

def test_low_risk_task_auto_executes():
    res = risk_scorer.score_task(
        prompt="Explain basic fluid mechanics in pipe flow",
        data_scope="public"
    )
    assert res["autonomy_tier"] == AutonomyTier.AUTO_EXECUTE
    assert res["requires_human_pause"] is False

def test_high_risk_task_requires_approval():
    high_risk_prompt = "Execute system shutdown and close main feed valve V-204 on crude line"
    res = risk_scorer.score_task(
        prompt=high_risk_prompt,
        data_scope="PID-101"
    )
    assert res["autonomy_tier"] in [AutonomyTier.HUMAN_APPROVAL_REQUIRED, AutonomyTier.DUAL_APPROVAL_REQUIRED]
    assert res["requires_human_pause"] is True

    # Test orchestrator response when user hasn't approved
    orch_res = agent_orchestrator.process_request(
        prompt=high_risk_prompt,
        user_approved=False
    )
    assert orch_res["status"] == "approval_required"

    # Test orchestrator response when user has explicitly approved
    orch_approved_res = agent_orchestrator.process_request(
        prompt=high_risk_prompt,
        user_approved=True
    )
    assert orch_approved_res["status"] == "completed"
