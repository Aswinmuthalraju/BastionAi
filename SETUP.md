# Setup Guide

Two paths: local development (fastest to iterate, what these instructions default to) or
Docker Compose (closer to a real deployment). Both end up running the same code.

## Prerequisites — local development

| Requirement | Why | Install |
|---|---|---|
| Python 3.13 | Backend runtime. **Not** 3.14 — `qdrant-client` and `kuzu` don't ship wheels for it yet at time of writing; **not** 3.9/3.10 — `qdrant-client` requires ≥3.10 and several other deps assume modern typing. | `brew install python@3.13` |
| Node.js ≥ 20 | Frontend build | `brew install node` or nvm |
| [Ollama](https://ollama.com) | Local LLM + embedding inference | `brew install ollama` (or the macOS app) |
| Tesseract OCR | Real OCR on uploaded diagrams | `brew install tesseract` |

Apple Silicon, 8 GB RAM is the minimum this was built and verified against. A 7B model takes
roughly 40 seconds to load on first request after Ollama starts (cold start), then responds
in a few seconds per request once warm. This is a real hardware constraint, not a bug — see
[Production model swap](#production-model-swap) to remove it.

## 1. Start Ollama and pull models

```bash
ollama serve &                      # if not already running as a background service
ollama pull qwen2.5:7b              # general reasoning / RAG / drift comparisons
ollama pull qwen2.5-coder:7b        # code-tagged tasks
ollama pull nomic-embed-text        # embeddings — required, has no substitute in this stack
```

Verify:

```bash
curl -s http://localhost:11434/api/tags
```

## 2. Backend

```bash
cd backend
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/seed_documents.py    # optional but recommended — ingests 4 real reference PDFs
uvicorn main:app --reload           # http://localhost:8000
```

Confirm everything is actually reachable (not just that the process started):

```bash
curl -s http://localhost:8000/v1/health | python3 -m json.tool
```

`"status": "healthy"` means Ollama, Qdrant, and the graph store are all genuinely responding.
`"degraded"` names which one isn't — check that subsystem before assuming the app works.

### First-run accounts

Seeded automatically on first backend startup (`app/auth/providers.py`), stored as real
Argon2id hashes in SQLite:

| Username | Password | Role | Scope |
|---|---|---|---|
| `operator` | `Refinery-Ops-2026!` | operator | public, refinery_ops, PID-101 |
| `engineer` | `Process-Auto-2026!` | engineer | + unreleased_design |
| `admin` | `Sovereign-Audit-2026!` | admin | `*` (everything, plus Console access) |

**Rotate these before any real deployment.** They exist only so the app is usable on first
run; there is no other bypass.

## 3. Frontend

```bash
cd frontend
npm install
npm run dev                         # http://localhost:3000, proxies /v1 to :8000
```

Open `http://localhost:3000`, sign in with one of the accounts above.

## Running tests

```bash
cd backend && source .venv/bin/activate
pytest tests/ -v
```

The suite makes real calls to Ollama (injection classification, drift embeddings) — it will
be slow (~30–40s) and will fail if Ollama isn't running with the models above pulled. This is
intentional: these tests exercise the real pipeline, not a mock of it.

```bash
cd frontend
npm run build
npm run verify        # Playwright: screenshots every screen at 1440px and 375px,
                       # checks for horizontal overflow, tabs through and checks
                       # focus-visible rings, and captures a prefers-reduced-motion pass.
```

Screenshots land in `frontend/verification/`.

## Docker Compose

```bash
cp .env.example .env          # set BASTION_JWT_SECRET — compose refuses to start without it
docker compose up --build
docker compose exec ollama ollama pull qwen2.5:7b
docker compose exec ollama ollama pull qwen2.5-coder:7b
docker compose exec ollama ollama pull nomic-embed-text
docker compose exec backend python scripts/seed_documents.py
```

Frontend on `:3000`, backend on `:8000`, Ollama on `:11434`. `backend_data` and
`ollama_models` are named volumes — data and pulled models survive `docker compose down`
(use `-v` to actually wipe them).

## Configuration reference

All backend config is environment variables read in `backend/app/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `BASTION_DATA_DIR` | `backend/data` | SQLite DB, embedded Qdrant, embedded Kùzu, uploaded files |
| `BASTION_LLM_BASE_URL` | `http://localhost:11434/v1` | OpenAI-compatible chat endpoint |
| `BASTION_EMBEDDING_BASE_URL` | `http://localhost:11434` | Ollama embedding endpoint |
| `BASTION_EMBEDDING_MODEL` | `nomic-embed-text` | Must match a pulled Ollama embedding model |
| `BASTION_JWT_SECRET` | random per-process | **Set explicitly in production** — see below |
| `BASTION_JWT_TTL_MINUTES` | `480` | Session length |
| `BASTION_AUTH_PROVIDER` | `local` | `local` (SQLite + Argon2) or `ldap` |
| `BASTION_LDAP_SERVER_URI` / `BASTION_LDAP_BASE_DN` | — | Required if `BASTION_AUTH_PROVIDER=ldap` |
| `BASTION_MANIFEST_PATH` | `backend/config/models_manifest.yaml` | Model routing manifest |

## Production model swap

`backend/config/models_manifest.yaml` has one entry per logical model. Each entry's
`endpoint` is any OpenAI-compatible `/v1/chat/completions` server. To move off local Ollama
onto a real vLLM cluster, change only the manifest:

```yaml
  - id: "llama-3.3-70b"
    endpoint: "http://vllm-general.internal:8000/v1"
    served_model: "meta-llama/Llama-3.3-70B-Instruct"
    ...
```

No application code changes — `app/providers/llm.py` already speaks the OpenAI chat schema.
The same applies to the embedding endpoint (`BASTION_EMBEDDING_BASE_URL`) if you move to a
dedicated embedding server.

## Production LDAP

`app/auth/providers.py` includes `LDAPAuthProvider`, a real `ldap3` bind implementation. It
is inactive by default because no LDAP server exists in a typical dev/sandbox environment.
To activate:

```bash
export BASTION_AUTH_PROVIDER=ldap
export BASTION_LDAP_SERVER_URI=ldaps://your-ldap-host:636
export BASTION_LDAP_BASE_DN="dc=example,dc=com"
```

Review the `uid=`/attribute assumptions in `LDAPAuthProvider.authenticate` against your
directory schema before relying on it — it was written against a generic OpenLDAP layout and
has not been tested against a real directory server (none was available to test against in
this environment).

## Scaling the vector store / graph store beyond a single box

Both Qdrant and Kùzu currently run embedded (in-process, on-disk at `BASTION_DATA_DIR`) —
correct for a single-node deployment, but not for multi-instance horizontal scaling. To scale
out: run a real Qdrant server and change `QdrantClient(path=...)` to
`QdrantClient(url=...)` in `app/rag/vector_store.py`; Kùzu's embedded model does not have a
built-in server mode, so scaling the graph store further would mean moving to a client-server
graph database (e.g., Neo4j) behind the same `GraphStore` interface in `app/graph/store.py`.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| First chat request takes ~40s | Ollama cold-loading the model into memory | Expected once per Ollama restart; subsequent requests are a few seconds |
| `/v1/health` shows `llm_provider.reachable: false` | Ollama isn't running or wrong port | `ollama serve`; check `BASTION_LLM_BASE_URL` |
| Sessions all invalidated after a backend restart | `BASTION_JWT_SECRET` wasn't set — a fresh random secret was generated | Set `BASTION_JWT_SECRET` in your environment |
| OCR always returns empty text | Tesseract not installed / not on PATH | `brew install tesseract`, confirm with `tesseract --version` |
| `pip install` fails on `qdrant-client` | Wrong Python version | Confirm `python3.13 -m venv .venv` was actually used — check `python --version` inside the venv |
| Frontend shows "backend is unreachable" | Backend not running, or Vite proxy misconfigured | Confirm `uvicorn` is running on :8000; check `vite.config.ts` proxy target |
