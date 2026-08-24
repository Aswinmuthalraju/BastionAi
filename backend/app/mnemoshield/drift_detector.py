from typing import Any, Dict, List

from app.providers.embeddings import EmbeddingUnavailableError, embedding_provider

DEFAULT_PLAN_GRAPH = [
    "Inspect P&ID diagram 101 for feed pump P-101 and valve V-204",
    "Retrieve ultrasonic wall thickness inspection findings for line L-204",
    "Calculate fluid velocity and pump flow rate",
    "Generate final refinery compliance and overhaul summary report",
]

# Explicit bypass/override language escalates regardless of embedding similarity —
# an attacker can phrase a dangerous action so it's semantically "close" to a
# benign plan step while still being an attempt to skip safety controls.
ESCALATION_KEYWORDS = ["override", "delete", "shutdown", "shut down", "bypass", "purge", "secret"]


class TrajectoryDriftDetector:
    """
    Measures real embedding-space distance between an agent's proposed action
    and the expected plan-graph node, using the same embedding model that
    powers RAG retrieval — not a hand-rolled term-frequency vector.
    """

    def evaluate_action_drift(
        self,
        proposed_action: str,
        expected_step_index: int = 0,
        plan_nodes: List[str] = None,
        drift_threshold: float = 0.55,
    ) -> Dict[str, Any]:
        plan_nodes = plan_nodes or DEFAULT_PLAN_GRAPH
        step_idx = min(expected_step_index, len(plan_nodes) - 1)
        expected_node = plan_nodes[step_idx]

        degraded = False
        try:
            vec_proposed = embedding_provider.embed(proposed_action)
            vec_expected = embedding_provider.embed(expected_node)
            similarity = embedding_provider.cosine_similarity(vec_proposed, vec_expected)
            # Cosine on real sentence embeddings clusters in a narrower, higher band
            # than TF-IDF overlap; rescale so the existing 0.55 threshold still
            # separates on-track from off-track action pairs meaningfully.
            similarity = max(0.0, min(1.0, (similarity - 0.35) / 0.55))
        except EmbeddingUnavailableError:
            # No fabricated score: mark degraded and force human review instead of
            # silently declaring "on track" when we can't actually measure it.
            degraded = True
            similarity = 0.0

        drift_score = round(1.0 - similarity, 3)

        action_lower = proposed_action.lower()
        if any(w in action_lower for w in ESCALATION_KEYWORDS):
            drift_score = max(drift_score, 0.85)

        is_drifted = degraded or (drift_score >= drift_threshold)

        return {
            "drift_score": drift_score,
            "drift_threshold": drift_threshold,
            "is_drifted": is_drifted,
            "expected_node": expected_node,
            "proposed_action": proposed_action,
            "step_index": step_idx,
            "risk_escalation_required": is_drifted,
            "recommended_autonomy_tier": "dual_approval_required" if is_drifted else "auto_execute",
            "degraded": degraded,
        }


drift_detector = TrajectoryDriftDetector()
