from typing import Any, Dict, List, Optional

from app.agent.risk_scorer import risk_scorer
from app.agent.tools import tool_registry
from app.audit.logger import audit_logger
from app.graph.store import extract_equipment_ids, graph_store
from app.ingest.pipeline import get_document
from app.mnemoshield.drift_detector import drift_detector
from app.mnemoshield.dual_rail_security import dual_rail_security
from app.mnemoshield.memory_module import memory_module
from app.multimodal.ocr import ocr_processor
from app.passport.model import AutonomyTier, TaskPassport
from app.providers.llm import LLMUnavailableError, llm_provider
from app.rag.evidence_ledger import evidence_ledger
from app.rag.vector_store import vector_store_service
from app.router.classifier import classifier
from app.router.engine import router_engine
from app.security.quarantine import quarantine_manager

SYSTEM_PROMPT = (
    "You are BastionAI, an on-premise engineering assistant deployed inside a sovereign, "
    "air-gapped industrial workbench. Answer precisely from what you actually know or from "
    "the source material given to you. If you are not certain, or the provided material "
    "doesn't contain the answer, say so plainly instead of guessing."
)


def _plan_tools(prompt: str, classification: Dict[str, Any]) -> List[str]:
    """Derives the real set of tools this request would exercise, so risk scoring
    reflects the actual planned action instead of a hardcoded ['rag_search']."""
    tags = classification["all_tags"]
    prompt_lower = prompt.lower()
    tools: List[str] = []

    if "vision" in tags or "pid_diagram" in tags:
        tools += ["pid_extractor", "graph_query"]
    if "code" in tags:
        tools.append("math_calculator")
    if any(t in tags for t in ("document_summary", "rag", "financial", "negotiation", "contract")):
        tools.append("rag_search")
    if any(w in prompt_lower for w in ("shut down", "shutdown")):
        tools.append("system_shutdown")
    if "valve" in prompt_lower and any(w in prompt_lower for w in ("close", "open", "override", "bypass")):
        tools.append("valve_override")
    if any(w in prompt_lower for w in ("purge", "delete")):
        tools.append("database_purge")
    if "shell" in prompt_lower:
        tools.append("shell_execution")

    return tools or ["rag_search"]


class AgentOrchestrator:
    """
    Sovereign Agent Orchestrator with MnemoShield Causal Integrity Enforcement.
    Every stage below makes a real call (LLM inference, embedding, vector
    search, graph query) and returns real failures when a dependency is down —
    nothing here fabricates a response.
    """

    def process_request(
        self,
        prompt: str,
        user_id: str = "eng-user-01",
        user_role: str = "operator",
        data_scope: List[str] = None,
        allowed_models: List[str] = None,
        image_doc_id: Optional[str] = None,
        user_approved: bool = False,
        expected_step_index: int = 0,
    ) -> Dict[str, Any]:

        data_scope = data_scope or ["public", "refinery_ops", "PID-101"]
        allowed_models = allowed_models or ["llama-3.3-70b", "qwen2.5-coder", "qwen2-vl"]
        provenance: List[Dict[str, Any]] = []

        # 1. Dual-Rail Security Injection Screening
        screen_res = dual_rail_security.scan_content(
            text=prompt,
            source_filename="User_Input_Prompt.pdf",
            page_number=1,
        )
        provenance.append({"stage": "screened", "status": "blocked" if screen_res["is_malicious"] else "clear", "detail": screen_res})

        if screen_res["is_malicious"]:
            quarantine_item = quarantine_manager.quarantine(
                content=prompt, source=screen_res["source_doc"], page=screen_res["page_number"], trace=screen_res["trace_message"],
            )
            audit_logger.log_event(
                user_id=user_id,
                action=f"PROMPT_INJECTION_QUARANTINE (Rail: {screen_res['detected_by']})",
                risk_tier=AutonomyTier.DUAL_APPROVAL_REQUIRED.value,
                outcome="BLOCKED",
                details=screen_res["trace_message"],
            )
            return {
                "status": "quarantined_and_blocked",
                "quarantine_id": quarantine_item["item_id"],
                "detected_by": screen_res["detected_by"],
                "trace_message": screen_res["trace_message"],
                "evidence_citations": [],
                "agent_response": screen_res["trace_message"],
                "provenance": provenance,
            }

        # 2. Task classification (drives both routing and real tool planning below)
        classification = classifier.classify(prompt, has_image=bool(image_doc_id))
        planned_tools = _plan_tools(prompt, classification)

        # 3. Trajectory Drift Detection (real embedding cosine)
        drift_res = drift_detector.evaluate_action_drift(proposed_action=prompt, expected_step_index=expected_step_index)
        provenance.append({"stage": "drift_checked", "status": "drifted" if drift_res["is_drifted"] else "on_track", "detail": drift_res})

        # 4. Risk Scoring against the actually planned tools
        risk_res = risk_scorer.score_task(prompt, data_scope=data_scope[0], requested_tools=planned_tools)

        if drift_res["is_drifted"]:
            risk_res["total_risk_score"] = max(risk_res["total_risk_score"], 8.5)
            risk_res["autonomy_tier"] = AutonomyTier.DUAL_APPROVAL_REQUIRED
            risk_res["requires_human_pause"] = True
            risk_res["risk_factors"].append(f"Trajectory Drift Interception: Action drifted from expected plan node '{drift_res['expected_node']}'.")

        autonomy_tier = risk_res["autonomy_tier"]

        passport = TaskPassport(
            user_id=user_id, user_role=user_role, data_scope=data_scope, allowed_models=allowed_models,
            allowed_tools=planned_tools, autonomy_required=autonomy_tier,
            risk_score=risk_res["total_risk_score"], risk_factors=risk_res["risk_factors"],
        )
        provenance.append({"stage": "scored", "status": autonomy_tier.value, "detail": risk_res})

        audit_logger.log_event(
            user_id=user_id, action="TRAJECTORY_DRIFT_EVALUATION", risk_tier=autonomy_tier.value,
            outcome="DRIFT_DETECTED" if drift_res["is_drifted"] else "ON_TRACK",
            details=f"Drift Score: {drift_res['drift_score']} (Threshold: {drift_res['drift_threshold']})",
        )

        # 5. Human Approval Gate
        if risk_res["requires_human_pause"] and not user_approved:
            return {
                "status": "approval_required",
                "passport": passport.model_dump(),
                "risk_analysis": risk_res,
                "drift_analysis": drift_res,
                "message": f"Action requires {autonomy_tier.value.upper().replace('_', ' ')} approval before execution.",
                "trace_message": None,
                "evidence_citations": [],
                "provenance": provenance,
            }

        # 6. Route to a model per the manifest
        route_res = router_engine.route(prompt=prompt, passport=passport, has_image=bool(image_doc_id))
        if route_res["status"] == "rejected":
            return {"status": "rejected", "reason": route_res["reason"], "passport": passport.model_dump(), "trace_message": None, "evidence_citations": [], "provenance": provenance}

        selected_model = route_res["model_name"]
        endpoint = route_res["endpoint"]
        served_model = route_res["served_model"]
        primary_tag = route_res["primary_tag"]
        provenance.append({"stage": "routed", "status": "ok", "detail": {"model_id": route_res["model_id"], "served_model": served_model, "endpoint": endpoint, "tag": primary_tag}})

        retrieved_chunks: List[Dict[str, Any]] = []
        graph_data = None
        generation_meta: Dict[str, Any] = {}

        try:
            if (primary_tag == "vision" or image_doc_id) and image_doc_id:
                response_text, graph_data, generation_meta = self._run_vision(prompt, image_doc_id, endpoint, served_model)
                memory_module.add_entry(f"Analyzed uploaded diagram (doc {image_doc_id}) with {selected_model}.", category="action", importance=4.0)

            elif primary_tag == "code":
                response_text, generation_meta = self._run_generation(prompt, endpoint, served_model)
                memory_module.add_entry(f"Generated code for: '{prompt[:60]}' using {selected_model}.", category="conclusion", importance=3.5)

            elif any(t in planned_tools for t in ("valve_override", "system_shutdown")):
                response_text, generation_meta = self._run_equipment_command(prompt, planned_tools, user_id)
                memory_module.add_entry(f"Executed equipment command: '{prompt[:60]}'", category="action", importance=4.5)

            else:
                retrieved_chunks = vector_store_service.search(query=prompt, user_scopes=passport.data_scope, user_role=passport.user_role)
                provenance.append({"stage": "retrieved", "status": "ok", "detail": {"chunk_count": len(retrieved_chunks)}})

                for chunk in retrieved_chunks:
                    chunk_scan = dual_rail_security.scan_content(text=chunk["content"], source_filename=chunk["source_doc"], page_number=chunk["page_number"])
                    if chunk_scan["is_malicious"]:
                        quarantine_manager.quarantine(content=chunk["content"], source=chunk_scan["source_doc"], page=chunk_scan["page_number"], trace=chunk_scan["trace_message"])
                        return {"status": "quarantined_and_blocked", "detected_by": chunk_scan["detected_by"], "trace_message": chunk_scan["trace_message"], "evidence_citations": [], "agent_response": chunk_scan["trace_message"], "provenance": provenance}

                response_text, generation_meta = self._run_rag_generation(prompt, retrieved_chunks, endpoint, served_model)
                memory_module.add_entry(f"Answered RAG query: '{prompt[:60]}'", category="action", importance=3.0)

        except LLMUnavailableError as exc:
            audit_logger.log_event(user_id=user_id, action="MODEL_UNREACHABLE", risk_tier=autonomy_tier.value, outcome="FAILED", details=str(exc))
            return {
                "status": "error", "reason": f"Model endpoint for '{selected_model}' is unreachable: {exc}",
                "passport": passport.model_dump(), "trace_message": None, "evidence_citations": [], "provenance": provenance,
            }

        provenance.append({"stage": "executed", "status": "ok", "detail": generation_meta})
        citations = evidence_ledger.generate_ledger(retrieved_chunks, model_used=selected_model)

        audit_logger.log_event(
            user_id=user_id, action="TASK_COMPLETED", risk_tier=autonomy_tier.value,
            outcome="SUCCESS", details=f"Routed to {selected_model} (Task: {passport.task_id}, Drift: {drift_res['drift_score']})",
        )

        return {
            "status": "completed", "passport": passport.model_dump(), "route_info": route_res,
            "agent_response": response_text, "evidence_citations": citations, "graph_data": graph_data,
            "drift_analysis": drift_res, "trace_message": None, "risk_analysis": risk_res, "provenance": provenance,
        }

    def _run_generation(self, prompt: str, endpoint: str, served_model: str):
        result = llm_provider.chat(
            endpoint=endpoint, served_model=served_model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": prompt}],
            max_tokens=600,
        )
        return result["content"], {"latency_s": result["latency_s"], "completion_tokens": result["completion_tokens"], "served_model": served_model}

    def _run_rag_generation(self, prompt: str, chunks: List[Dict[str, Any]], endpoint: str, served_model: str):
        if chunks:
            context = "\n\n".join(f"[Source: {c['source_doc']} p.{c['page_number']}] {c['content']}" for c in chunks)
        else:
            context = "(No matching documents were found within the operator's authorized data scope.)"

        result = llm_provider.chat(
            endpoint=endpoint, served_model=served_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + " Answer strictly from the source excerpts provided. Name which source you used."},
                {"role": "user", "content": f"Question: {prompt}\n\nSource excerpts:\n{context}"},
            ],
            max_tokens=500,
        )
        return result["content"], {"latency_s": result["latency_s"], "completion_tokens": result["completion_tokens"], "served_model": served_model, "sources_used": len(chunks)}

    def _run_equipment_command(self, prompt: str, planned_tools: List[str], actor_user_id: str):
        """
        Executes a physical-equipment command against the real (simulated)
        equipment-state machine — a deterministic tool call, not text generated
        by a language model pretending an action happened.
        """
        equipment_ids = extract_equipment_ids(prompt)
        if not equipment_ids:
            result = {"status": "rejected", "reason": "No specific equipment ID (e.g. V204, P101) was found in the request — refusing an ambiguous physical command."}
            return f"Command rejected: {result['reason']}", {"tool": "valve_override", "tool_result": result}

        prompt_lower = prompt.lower()
        target_id = equipment_ids[0]
        is_pump = target_id.startswith("P")
        if any(w in prompt_lower for w in ("shut down", "shutdown", "close")):
            target_state = "stopped" if is_pump else "closed"
        elif any(w in prompt_lower for w in ("open", "start")):
            target_state = "running" if is_pump else "open"
        else:
            target_state = "stopped" if is_pump else "closed"

        result = tool_registry.valve_override(target_id, target_state, actor_user_id=actor_user_id)

        if result["status"] == "executed":
            text = (
                f"Equipment command executed. {target_id}: {result['previous_state']} → {result['new_state']}.\n"
                f"{result['note']}"
            )
        else:
            text = f"Command rejected: {result.get('reason', 'unknown error')}"

        return text, {"tool": "valve_override", "tool_result": result}

    def _run_vision(self, prompt: str, image_doc_id: str, endpoint: str, served_model: str):
        doc = get_document(image_doc_id)
        if doc is None:
            raise LLMUnavailableError(f"Referenced image document '{image_doc_id}' was not found. Upload it via /v1/documents/upload first.")

        ocr_result = ocr_processor.process_image(doc["stored_path"])
        graph_data = None
        if ocr_result["detected_equipment_ids"]:
            graph_data = graph_store.query_equipment_lineage(ocr_result["detected_equipment_ids"][0])

        result = llm_provider.chat(
            endpoint=endpoint, served_model=served_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT + " You are given real OCR text extracted from an uploaded engineering diagram. Describe only what the extracted text actually supports; if it's sparse or unclear, say so rather than inventing equipment."},
                {"role": "user", "content": f"Request: {prompt}\n\nOCR-extracted text from the uploaded file ({doc['filename']}):\n{ocr_result['raw_text'] or '(no legible text detected)'}"},
            ],
            max_tokens=500,
        )
        meta = {"latency_s": result["latency_s"], "completion_tokens": result["completion_tokens"], "served_model": served_model, "ocr_detected_ids": ocr_result["detected_equipment_ids"]}
        return result["content"], graph_data, meta


agent_orchestrator = AgentOrchestrator()
