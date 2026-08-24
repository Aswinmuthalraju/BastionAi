"""
Seeds the workbench with reference documents so it isn't empty on first run.

This is NOT fake data standing in for computation: each document below is
rendered into a real PDF and pushed through the exact same ingestion pipeline
a real upload uses (app.ingest.pipeline.ingest_document) — real text
extraction, real dual-rail screening per page, real embeddings, real Qdrant
upsert, real graph-mention linking. Nothing about search results, citations,
or bounding boxes is special-cased for these documents.

Idempotent: skips any document whose filename has already been ingested.

Usage:
    cd backend && source .venv/bin/activate && python scripts/seed_documents.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fpdf import FPDF

from app.db import get_db, init_db
from app.ingest.pipeline import ingest_document

DOCUMENTS = [
    {
        "filename": "Refinery_PID_Diagram_101.pdf",
        "data_scope": "PID-101",
        "allowed_roles": ["operator", "engineer", "admin"],
        "text": (
            "P&ID Diagram 101-A: Crude Oil Feed System.\n\n"
            "Crude Oil Feed Line L-204 connects Storage Tank T-101 to High-Pressure "
            "Feed Pump P-101. Hydrocarbon Isolation Valve V-204 is positioned upstream "
            "of P-101 on the discharge side. Line rating: Class 300, 6-inch diameter.\n\n"
            "Normal operating state: V-204 is Normally Open. Pump P-101 is a centrifugal "
            "pump rated for continuous duty. Discharge is governed by SOP-771."
        ),
    },
    {
        "filename": "Refinery_Inspection_Report_2026.pdf",
        "data_scope": "refinery_ops",
        "allowed_roles": ["operator", "engineer", "auditor", "admin"],
        "text": (
            "Annual Inspection Findings 2026 - Crude Feed System.\n\n"
            "Ultrasonic thickness measurement on Line L-204, downstream of Valve V-204, "
            "shows 4.2mm wall thickness. Minimum allowable threshold per design "
            "specification is 3.5mm. Result: PASS.\n\n"
            "Inspection reference: INSP-2026-9. Next scheduled overhaul: October 2026. "
            "No corrosion anomalies detected on Pump P-101 casing or Tank T-101 shell."
        ),
    },
    {
        "filename": "Pump_P101_Operating_SOP.pdf",
        "data_scope": "refinery_ops",
        "allowed_roles": ["operator", "engineer", "admin"],
        "text": (
            "Standard Operating Procedure SOP-771 - Pump P-101 Vibration Bypass Procedure.\n\n"
            "Section 4.2: In the event of high vibration alarms on Pump P-101, open bypass "
            "valve V-204-B immediately before closing main feed Valve V-204. Do not close "
            "V-204 without first confirming V-204-B is fully open, to avoid deadheading the pump.\n\n"
            "Any shutdown of V-204 outside routine maintenance requires dual operator sign-off "
            "per the site risk-autonomy policy."
        ),
    },
    {
        "filename": "Supplier_Contract_ApexFlow_2026.pdf",
        "data_scope": "confidential_negotiation",
        "allowed_roles": ["executive", "admin"],
        "text": (
            "Confidential Supplier Agreement 2026 - Apex Flow Systems.\n\n"
            "Hydrocarbon Valve Unit V-204 replacement units purchased at $45,000 per unit "
            "under a 5-year warranty from Apex Flow Systems. Contract terms are commercially "
            "confidential and restricted to executive and admin scopes."
        ),
    },
]


def _render_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    return bytes(pdf.output())


def main():
    init_db()

    with get_db() as conn:
        existing = {r["filename"] for r in conn.execute("SELECT filename FROM documents").fetchall()}

    for doc in DOCUMENTS:
        if doc["filename"] in existing:
            print(f"skip  (already ingested) {doc['filename']}")
            continue

        result = ingest_document(
            file_bytes=_render_pdf(doc["text"]),
            filename=doc["filename"],
            content_type="application/pdf",
            data_scope=doc["data_scope"],
            allowed_roles=doc["allowed_roles"],
            uploaded_by="seed-script",
        )
        print(f"{result['status']:12} {doc['filename']}  "
              f"(pages={result['page_count']}, indexed={result['indexed_chunks']}, "
              f"mentions={result['mentioned_equipment']})")


if __name__ == "__main__":
    main()
