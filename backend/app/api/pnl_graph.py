from fastapi import APIRouter, Depends, HTTPException

from app.deps import get_current_user
from app.graph.store import graph_store
from app.ingest.pipeline import get_document
from app.multimodal.ocr import ocr_processor

router = APIRouter()


@router.get("/graph/lineage/{equipment_id}")
def get_equipment_lineage(equipment_id: str = "P101", user: dict = Depends(get_current_user)):
    """Returns a real Cypher graph traversal for the given equipment node."""
    return graph_store.query_equipment_lineage(equipment_id)


@router.post("/multimodal/parse-pid/{doc_id}")
def parse_pid_schematic(doc_id: str, user: dict = Depends(get_current_user)):
    """Runs real OCR against a previously uploaded diagram (see POST /v1/documents/upload)."""
    doc = get_document(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Document '{doc_id}' does not exist. Upload it first via POST /v1/documents/upload.")

    ocr_result = ocr_processor.process_image(doc["stored_path"])
    graph_lineage = None
    if ocr_result["detected_equipment_ids"]:
        graph_lineage = graph_store.query_equipment_lineage(ocr_result["detected_equipment_ids"][0])

    return {"ocr_extraction": ocr_result, "graph_lineage": graph_lineage}
