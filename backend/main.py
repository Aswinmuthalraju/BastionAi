import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.documents import router as documents_router
from app.api.mnemoshield import router as mnemoshield_router
from app.api.pnl_graph import router as graph_router
from app.auth.providers import LocalAuthProvider
from app.db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    LocalAuthProvider().seed_if_empty()
    yield


app = FastAPI(
    title="BastionAI Gateway with MnemoShield Integration",
    description="Sovereign On-Premise Agentic AI Workbench & MnemoShield Causal Integrity Enforcement",
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/v1", tags=["Chat & Router"])
app.include_router(graph_router, prefix="/v1", tags=["Knowledge Graph & Multimodal"])
app.include_router(documents_router, prefix="/v1", tags=["Documents & Ingestion"])
app.include_router(mnemoshield_router, prefix="/v1", tags=["MnemoShield Causal Integrity"])
app.include_router(admin_router, prefix="/v1", tags=["Admin & Audit"])
app.include_router(auth_router, prefix="/v1", tags=["Auth"])


@app.get("/")
def root():
    return {"system": "BastionAI Sovereign Workbench with MnemoShield Integration", "docs": "/docs"}


@app.get("/v1/health")
def health():
    """
    Reports what is genuinely reachable right now — never a hardcoded 'HEALTHY'.
    A degraded subsystem is surfaced here instead of masked by a fallback response.
    """
    checks = {}

    try:
        r = httpx.get(config.LLM_BASE_URL.rsplit("/v1", 1)[0] + "/api/tags", timeout=3.0)
        checks["llm_provider"] = {"reachable": r.status_code == 200, "endpoint": config.LLM_BASE_URL}
    except httpx.HTTPError as exc:
        checks["llm_provider"] = {"reachable": False, "endpoint": config.LLM_BASE_URL, "error": str(exc)}

    try:
        from app.rag.vector_store import vector_store_service
        checks["vector_store"] = {"reachable": True, "chunk_count": vector_store_service.count()}
    except Exception as exc:
        checks["vector_store"] = {"reachable": False, "error": str(exc)}

    try:
        from app.graph.store import graph_store
        graph_store.query_equipment_lineage("P101")
        checks["graph_store"] = {"reachable": True}
    except Exception as exc:
        checks["graph_store"] = {"reachable": False, "error": str(exc)}

    overall = all(c.get("reachable") for c in checks.values())
    return {"status": "healthy" if overall else "degraded", "checks": checks}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
