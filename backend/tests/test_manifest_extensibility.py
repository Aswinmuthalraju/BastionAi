import os
import yaml
import tempfile
from app.router.registry import ModelRegistry, ModelManifestItem
from app.router.engine import RouterEngine
from app.passport.model import TaskPassport

def test_add_third_model_via_manifest_only():
    """
    Core proof point: Adding a 3rd or N-th model via manifest YAML requires NO router code changes
    and is immediately routable by task tag.
    """
    manifest_content = """
models:
  - id: "llama-3.3-70b"
    name: "Llama 3.3 70B"
    endpoint: "http://vllm-general:8000/v1"
    modality: "text"
    context_window: 128000
    task_tags: ["reasoning", "general"]
    is_default: true

  - id: "qwen2.5-coder"
    name: "Qwen 2.5 Coder"
    endpoint: "http://vllm-coder:8000/v1"
    modality: "text"
    context_window: 65536
    task_tags: ["code"]
    is_default: false

  - id: "custom-financial-llm"
    name: "Custom Sovereign Financial LLM 14B"
    endpoint: "http://vllm-financial:8000/v1"
    modality: "text"
    context_window: 32768
    task_tags: ["financial", "negotiation", "contract"]
    is_default: false
"""
    with tempfile.NamedTemporaryFile("w+", suffix=".yaml", delete=False) as f:
        f.write(manifest_content)
        temp_manifest_path = f.name

    try:
        # Load registry from new manifest
        registry = ModelRegistry(manifest_path=temp_manifest_path)
        router = RouterEngine(registry=registry)

        # Confirm 3 models loaded
        models = registry.list_models()
        assert len(models) == 3
        assert any(m.id == "custom-financial-llm" for m in models)

        # Create Task Passport permitting the new model
        passport = TaskPassport(
            allowed_models=["llama-3.3-70b", "qwen2.5-coder", "custom-financial-llm"]
        )

        # Route a prompt matching the new model's tag
        route_result = router.route(
            prompt="Analyze vendor negotiation terms for confidential contract SOP",
            passport=passport
        )

        # Verify router picked the newly registered model without code changes
        assert route_result["status"] == "routed"
        assert route_result["model_id"] == "custom-financial-llm"
    finally:
        if os.path.exists(temp_manifest_path):
            os.remove(temp_manifest_path)
