# BastionAI

A sovereign, on-premise AI workbench for industrial operators — refineries, PSUs, and
defence-linked environments — with **MnemoShield**: a causal-integrity layer that screens
every request for injection, scores risk before executing anything irreversible, checks
proposed actions against a declared plan, and keeps a tamper-evident record of what happened
and why.

This is not a demo shell. Every screen is backed by real computation: real embedding-based
retrieval, a real embedded graph database, real LLM inference, real password hashing and
session tokens, and a real hash-chained audit trail persisted to disk. Where genuine
production infrastructure isn't available in a given environment (a GPU cluster, an
enterprise LDAP server), that boundary is documented explicitly rather than papered over —
see [Capability table](#capability-table) below.

## What it does

- **Chat workbench** — ask an engineering question, request a calculation, or attach a
  diagram. Every response is accompanied by a **Provenance Spine**: the literal pipeline the
  request passed through (screen → drift-check → risk-score → route → retrieve → execute),
  each stage showing the real data behind it.
- **Risk-aware autonomy** — actions are scored on data sensitivity, tool danger, and
  reversibility. High-risk actions (closing a valve, shutting down equipment) halt in place
  and require explicit operator approval before executing.
- **Dual-rail injection defense** — a real LLM-based classifier and a regex rule layer run in
  parallel; either firing quarantines the input and blocks execution, with full attribution.
- **Evidence-backed RAG** — answers are grounded in real document retrieval (Qdrant, real
  embeddings) with citations naming the source document, page, and a genuine bounding region
  computed from the actual extracted text.
- **Trajectory drift detection** — proposed actions are compared against a declared plan
  using real sentence-embedding cosine similarity; off-plan actions are intercepted and
  escalated.
- **Documents** — upload PDFs, images, or text; each is screened, chunked, embedded, and
  indexed through the same pipeline a real ingestion service would use.
- **Console** (admin) — working memory, drift testing, the model registry, the audit trail
  (with hash-chain verification), and the quarantine vault.

## Architecture

```
Frontend (React + Vite + TypeScript)
  → /v1  (proxied by server.js in production, by Vite in dev)
Backend (FastAPI, Python 3.13)
  ├─ Argon2 password hashing + JWT sessions, server-enforced RBAC on every route
  ├─ SQLite — users, audit log (hash-chained), quarantine, memory, documents, equipment state
  ├─ Qdrant (embedded) — real HNSW vector search over real embeddings
  ├─ Kùzu (embedded) — real property graph, real Cypher queries
  └─ Ollama (OpenAI-compatible /v1/chat/completions + /api/embed)
       — local dev inference target; production points the same manifest at vLLM
```

The model manifest (`backend/config/models_manifest.yaml`) is the single source of truth for
routing. Adding an entry there — a new model ID, endpoint, and task tags — makes it routable
immediately, with no code changes.

## Capability table

| Capability | Status |
|---|---|
| Vector search (Qdrant), real embeddings | Real |
| Graph store (Kùzu), real Cypher | Real |
| LLM generation, injection classification, drift comparison | Real inference (local Ollama; same code path targets vLLM in production) |
| Password auth, sessions, server-side RBAC | Real (Argon2 + JWT) |
| Audit trail | Real, persisted, hash-chained |
| Document ingestion (PDF/image/text → chunks → embeddings → index) | Real |
| OCR on uploaded diagrams | Real (Tesseract) — no GPU vision model available locally, see below |
| Equipment control (valve/pump state) | Real software state machine — **not** connected to a physical plant; see below |
| LDAP authentication | Real `ldap3` bind implemented, **not active by default** — no LDAP server in this environment |
| Response token streaming | Not implemented — responses return once complete, not token-by-token |
| Document viewer bounding-box overlay | Not implemented — bounding boxes are computed and shown in chat citations, but the Documents page renders the raw file, not an annotated overlay |

Every "not implemented" line above is a deliberate, disclosed scope boundary, not a silently
half-built feature.

## Local development

See [SETUP.md](SETUP.md) for the full guide. In short:

```bash
# Backend
cd backend && python3.13 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
ollama pull qwen2.5:7b && ollama pull qwen2.5-coder:7b && ollama pull nomic-embed-text
python scripts/seed_documents.py
uvicorn main:app --reload

# Frontend
cd frontend && npm install && npm run dev
```

## Testing

```bash
cd backend && source .venv/bin/activate && pytest tests/ -v
cd frontend && npm run build && npm run verify   # Playwright: screenshots, focus, responsiveness
```

## Security notes

- First-run accounts and their passwords are listed in SETUP.md — **rotate them** before any
  real deployment.
- `BASTION_JWT_SECRET` must be set explicitly in production; if unset, a random secret is
  generated per process start (every restart invalidates existing sessions — fine for dev,
  not for production).
- The equipment-control tool operates a local simulator only. Wiring it to a real control
  system is out of scope for this codebase and would need its own safety review.
