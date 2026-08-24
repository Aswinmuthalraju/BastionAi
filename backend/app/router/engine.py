from typing import Dict, Any, Optional
from app.router.registry import global_registry, ModelManifestItem
from app.router.classifier import classifier
from app.passport.model import TaskPassport

class RouterEngine:
    """
    Model Routing Engine.
    Routes incoming prompts to the optimal model based on registry tags, 
    task classification, and Task Passport security policies.
    """
    def __init__(self, registry=None):
        self.registry = registry or global_registry

    def route(
        self,
        prompt: str,
        passport: TaskPassport,
        has_image: bool = False,
        requested_model: Optional[str] = None
    ) -> Dict[str, Any]:
        
        classification = classifier.classify(prompt, has_image=has_image)
        primary_tag = classification["primary_tag"]
        confidence = classification["confidence"]

        selected_model: Optional[ModelManifestItem] = None
        fallback_used = False
        rejection_reason = None

        # If user specifically requested a model
        if requested_model:
            candidate = self.registry.get_model(requested_model)
            if candidate:
                if passport.validate_model(candidate.id):
                    selected_model = candidate
                else:
                    rejection_reason = f"Requested model '{requested_model}' is forbidden by Task Passport policy."

        # If no specific model or requested model forbidden/invalid
        if not selected_model:
            candidates = self.registry.find_models_by_tag(primary_tag)
            
            # Filter candidates by Task Passport
            allowed_candidates = [m for m in candidates if passport.validate_model(m.id)]
            
            if allowed_candidates:
                selected_model = allowed_candidates[0]
            else:
                # Fallback logic: attempt default general reasoner
                default_model = self.registry.get_default_model()
                if passport.validate_model(default_model.id):
                    selected_model = default_model
                    fallback_used = True
                else:
                    # Search any allowed model
                    for m in self.registry.list_models():
                        if passport.validate_model(m.id):
                            selected_model = m
                            fallback_used = True
                            break

        if not selected_model:
            return {
                "status": "rejected",
                "reason": rejection_reason or "No allowed model available in Task Passport policy.",
                "passport": passport.model_dump(),
                "classification": classification
            }

        return {
            "status": "routed",
            "model_id": selected_model.id,
            "model_name": selected_model.name,
            "endpoint": selected_model.endpoint,
            "served_model": selected_model.served_model or selected_model.id,
            "modality": selected_model.modality,
            "primary_tag": primary_tag,
            "confidence": confidence,
            "fallback_used": fallback_used,
            "passport": passport.model_dump()
        }

router_engine = RouterEngine()
