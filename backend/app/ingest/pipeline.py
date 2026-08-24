import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pdfplumber

from app import config
from app.db import get_db
from app.graph.store import graph_store
from app.mnemoshield.dual_rail_security import dual_rail_security
from app.multimodal.ocr import ocr_processor
from app.rag.vector_store import vector_store_service
from app.security.quarantine import quarantine_manager

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".tiff", ".bmp"}


def _extract_pdf_pages(path: Path) -> List[Tuple[str, Dict[str, float]]]:
    """Real per-page text + a genuine bounding box covering the extracted words on that page."""
    pages = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            words = page.extract_words()
            if words:
                x0 = min(w["x0"] for w in words) / page.width
                x1 = max(w["x1"] for w in words) / page.width
                y0 = min(w["top"] for w in words) / page.height
                y1 = max(w["bottom"] for w in words) / page.height
                bbox = {"x1": round(x0, 3), "y1": round(y0, 3), "x2": round(x1, 3), "y2": round(y1, 3)}
            else:
                bbox = {"x1": 0.05, "y1": 0.05, "x2": 0.95, "y2": 0.95}
            pages.append((text, bbox))
    return pages


def _extract_image(path: Path) -> List[Tuple[str, Dict[str, float]]]:
    ocr_result = ocr_processor.process_image(str(path))
    return [(ocr_result["raw_text"], {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0})]


def _extract_text_file(path: Path) -> List[Tuple[str, Dict[str, float]]]:
    return [(path.read_text(encoding="utf-8", errors="replace"), {"x1": 0.0, "y1": 0.0, "x2": 1.0, "y2": 1.0})]


def ingest_document(
    file_bytes: bytes,
    filename: str,
    content_type: str,
    data_scope: str,
    allowed_roles: List[str],
    uploaded_by: str,
) -> Dict[str, Any]:
    doc_id = f"DOC-{uuid.uuid4().hex[:10].upper()}"
    suffix = Path(filename).suffix.lower()
    stored_path = config.UPLOADS_DIR / f"{doc_id}{suffix}"
    stored_path.write_bytes(file_bytes)

    status = "indexed"
    error = None
    indexed_chunks = 0
    quarantined_chunks = 0
    mentioned_equipment: List[str] = []
    full_text_parts: List[str] = []

    try:
        if suffix == ".pdf":
            pages = _extract_pdf_pages(stored_path)
        elif suffix in IMAGE_EXTENSIONS:
            pages = _extract_image(stored_path)
        else:
            pages = _extract_text_file(stored_path)

        for page_number, (text, bbox) in enumerate(pages, start=1):
            text = text.strip()
            if not text:
                continue
            full_text_parts.append(text)

            scan = dual_rail_security.scan_content(text, source_filename=filename, page_number=page_number)
            if scan["is_malicious"]:
                quarantine_manager.quarantine(content=text, source=filename, page=page_number, trace=scan["trace_message"])
                quarantined_chunks += 1
                continue

            chunk_id = f"{doc_id}-p{page_number}"
            vector_store_service.add_chunk(
                chunk_id=chunk_id, content=text, source_doc=filename, page_number=page_number,
                data_scope=data_scope, allowed_roles=allowed_roles, doc_id=doc_id, bounding_box=bbox,
            )
            indexed_chunks += 1

        if indexed_chunks == 0 and quarantined_chunks > 0:
            status = "quarantined"

        if full_text_parts:
            mentioned_equipment = graph_store.link_document_mentions(doc_id, filename, "\n".join(full_text_parts))

        page_count = len(pages)

    except Exception as exc:  # extraction failures are recorded, not hidden
        status = "failed"
        error = str(exc)
        page_count = 0

    with get_db() as conn:
        conn.execute(
            "INSERT INTO documents (doc_id, filename, stored_path, content_type, data_scope, allowed_roles, "
            "page_count, status, uploaded_by, uploaded_at, error) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (doc_id, filename, str(stored_path), content_type, data_scope, json.dumps(allowed_roles),
             page_count, status, uploaded_by, time.time(), error),
        )

    return {
        "doc_id": doc_id, "filename": filename, "status": status, "page_count": page_count,
        "indexed_chunks": indexed_chunks, "quarantined_chunks": quarantined_chunks,
        "mentioned_equipment": mentioned_equipment, "error": error,
    }


def list_documents(user_scopes: List[str], user_role: str) -> List[Dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM documents ORDER BY uploaded_at DESC").fetchall()

    visible = []
    for r in rows:
        roles = json.loads(r["allowed_roles"])
        scope_ok = "*" in user_scopes or r["data_scope"] in user_scopes
        role_ok = "admin" in user_role or user_role in roles
        if scope_ok and role_ok:
            visible.append(dict(r))
    return visible


def get_document(doc_id: str) -> Dict[str, Any]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM documents WHERE doc_id = ?", (doc_id,)).fetchone()
    return dict(row) if row else None
