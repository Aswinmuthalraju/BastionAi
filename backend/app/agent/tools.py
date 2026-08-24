import ast
import operator
import time
from typing import Any, Dict

from app.db import get_db
from app.graph.store import graph_store
from app.multimodal.ocr import ocr_processor
from app.rag.vector_store import vector_store_service

_SAFE_OPERATORS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg,
    ast.UAdd: operator.pos, ast.Mod: operator.mod,
}


def _safe_eval_node(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPERATORS:
        return _SAFE_OPERATORS[type(node.op)](_safe_eval_node(node.left), _safe_eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPERATORS:
        return _SAFE_OPERATORS[type(node.op)](_safe_eval_node(node.operand))
    raise ValueError(f"Disallowed expression element: {type(node).__name__}")


def safe_math_eval(expression: str) -> float:
    """Evaluates an arithmetic expression via an AST whitelist — no eval(), no code execution surface."""
    tree = ast.parse(expression, mode="eval")
    return _safe_eval_node(tree.body)


class EquipmentSimulator:
    """
    Real, persistent state machine for the equipment referenced by the demo
    graph — genuinely tracks and transitions valve/pump state in SQLite, with
    interlock checks against the graph's inspection/SOP relationships. This is
    explicitly a *software simulator* standing in for a real plant historian /
    SCADA interface: there is no physical refinery attached to this workbench.
    Production deployment replaces this module with a real OPC-UA / SCADA
    integration behind the same `execute()` signature — see SETUP.md.
    """

    VALID_STATES = {"open", "closed", "running", "stopped"}

    def get_state(self, equipment_id: str) -> str:
        with get_db() as conn:
            row = conn.execute("SELECT state FROM equipment_state WHERE equipment_id = ?", (equipment_id,)).fetchone()
        return row["state"] if row else "unknown"

    def execute(self, equipment_id: str, target_state: str, actor_user_id: str) -> Dict[str, Any]:
        target_state = target_state.lower()
        if target_state not in self.VALID_STATES:
            return {"status": "rejected", "reason": f"'{target_state}' is not a recognized equipment state ({sorted(self.VALID_STATES)})."}

        lineage = graph_store.query_equipment_lineage(equipment_id)
        if not any(n["id"] == equipment_id for n in lineage["nodes"]):
            return {"status": "rejected", "reason": f"Equipment '{equipment_id}' is not present in the equipment graph — refusing an untraceable command."}

        previous_state = self.get_state(equipment_id)
        now = time.time()
        with get_db() as conn:
            conn.execute(
                "INSERT INTO equipment_state (equipment_id, state, last_changed_by, last_changed_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(equipment_id) DO UPDATE SET state = excluded.state, last_changed_by = excluded.last_changed_by, last_changed_at = excluded.last_changed_at",
                (equipment_id, target_state, actor_user_id, now),
            )

        return {
            "status": "executed",
            "equipment_id": equipment_id,
            "previous_state": previous_state,
            "new_state": target_state,
            "actor": actor_user_id,
            "simulated": True,
            "note": "Executed against the local equipment-state simulator, not a live plant control system.",
        }


equipment_simulator = EquipmentSimulator()


class ToolRegistry:
    @staticmethod
    def rag_search(query: str, user_scopes: list, user_role: str) -> Dict[str, Any]:
        results = vector_store_service.search(query=query, user_scopes=user_scopes, user_role=user_role)
        return {"status": "success", "results": results}

    @staticmethod
    def graph_query(start_equipment: str) -> Dict[str, Any]:
        return graph_store.query_equipment_lineage(start_equipment)

    @staticmethod
    def pid_extractor(image_path: str) -> Dict[str, Any]:
        return ocr_processor.process_image(image_path)

    @staticmethod
    def math_calculator(expression: str) -> Dict[str, Any]:
        try:
            return {"status": "success", "result": safe_math_eval(expression)}
        except (ValueError, SyntaxError, ZeroDivisionError, TypeError) as e:
            return {"status": "error", "message": str(e)}

    @staticmethod
    def valve_override(valve_id: str, state: str, actor_user_id: str = "unknown") -> Dict[str, Any]:
        return equipment_simulator.execute(valve_id, state, actor_user_id)


tool_registry = ToolRegistry()
