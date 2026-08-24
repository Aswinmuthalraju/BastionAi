import os
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel

from app import config


class ModelManifestItem(BaseModel):
    id: str
    name: str
    endpoint: str
    modality: str
    context_window: int
    task_tags: List[str]
    is_default: bool = False
    # The concrete model actually invoked at `endpoint` (an OpenAI-compatible
    # /v1/chat/completions server). In production this equals the vLLM-served
    # model name. Locally it's whatever's pulled in Ollama.
    served_model: Optional[str] = None
    deployment_note: Optional[str] = None


class ModelRegistry:
    def __init__(self, manifest_path: Optional[str] = None):
        self.manifest_path = os.path.abspath(manifest_path or config.MANIFEST_PATH)
        self.models: Dict[str, ModelManifestItem] = {}
        self.reload()

    def reload(self):
        """Reload models from manifest file without restarting services."""
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"Manifest not found at {self.manifest_path}")

        with open(self.manifest_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        self.models = {}
        for item in data.get("models", []):
            model = ModelManifestItem(**item)
            self.models[model.id] = model

    def add_model(self, model_item: ModelManifestItem):
        """Add a model dynamically to the running registry (in-memory only until reload())."""
        self.models[model_item.id] = model_item

    def get_model(self, model_id: str) -> Optional[ModelManifestItem]:
        return self.models.get(model_id)

    def list_models(self) -> List[ModelManifestItem]:
        return list(self.models.values())

    def get_default_model(self) -> ModelManifestItem:
        for model in self.models.values():
            if model.is_default:
                return model
        return list(self.models.values())[0]

    def find_models_by_tag(self, tag: str) -> List[ModelManifestItem]:
        return [m for m in self.models.values() if tag in m.task_tags]


global_registry = ModelRegistry()
