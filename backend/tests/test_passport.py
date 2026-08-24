from app.passport.model import TaskPassport, AutonomyTier
from app.router.engine import router_engine

def test_passport_data_scope_validation():
    passport = TaskPassport(
        data_scope=["PID-101", "public"]
    )
    assert passport.validate_access("PID-101") is True
    assert passport.validate_access("CLASSIFIED-DEFENCE-009") is False

def test_passport_model_restriction():
    passport = TaskPassport(
        allowed_models=["qwen2.5-coder"]  # llama-3.3-70b excluded
    )
    
    # Requesting general reasoning task
    res = router_engine.route(
        prompt="Explain thermodynamic efficiency in distillation columns",
        passport=passport
    )
    
    # Must pick allowed qwen2.5-coder or report fallback
    assert res["status"] == "routed"
    assert res["model_id"] == "qwen2.5-coder"

def test_passport_rejection_when_no_model_allowed():
    passport = TaskPassport(
        allowed_models=[]  # Empty allowed models
    )
    res = router_engine.route(
        prompt="Write python script to calculate pump flow rate",
        passport=passport
    )
    assert res["status"] == "rejected"
    assert "No allowed model available" in res["reason"]
