import os
import secrets
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = Path(os.environ.get("BASTION_DATA_DIR", BACKEND_ROOT / "data")).resolve()
UPLOADS_DIR = DATA_DIR / "uploads"
QDRANT_PATH = str(DATA_DIR / "qdrant")
KUZU_PATH = str(DATA_DIR / "graph.kuzu")
SQLITE_PATH = str(DATA_DIR / "bastion.db")

for d in (DATA_DIR, UPLOADS_DIR):
    d.mkdir(parents=True, exist_ok=True)

# --- LLM / embedding provider -------------------------------------------------
# Local dev target is Ollama's OpenAI-compatible API. In production this is
# pointed at a vLLM cluster per model entry in models_manifest.yaml — the
# provider code makes a real HTTP call either way.
LLM_BASE_URL = os.environ.get("BASTION_LLM_BASE_URL", "http://localhost:11434/v1")
EMBEDDING_BASE_URL = os.environ.get("BASTION_EMBEDDING_BASE_URL", "http://localhost:11434")
EMBEDDING_MODEL = os.environ.get("BASTION_EMBEDDING_MODEL", "nomic-embed-text")
EMBEDDING_DIM = int(os.environ.get("BASTION_EMBEDDING_DIM", "768"))
LLM_TIMEOUT_SECONDS = float(os.environ.get("BASTION_LLM_TIMEOUT_SECONDS", "60"))

# --- Auth ----------------------------------------------------------------------
# "local" = real Argon2 + SQLite user store (this environment's default — no
# LDAP server is reachable from an air-gapped sandbox). "ldap" activates
# app.auth.providers.LDAPAuthProvider, a real ldap3 bind against
# BASTION_LDAP_SERVER_URI — see SETUP.md for production wiring.
AUTH_PROVIDER = os.environ.get("BASTION_AUTH_PROVIDER", "local")
LDAP_SERVER_URI = os.environ.get("BASTION_LDAP_SERVER_URI", "")
LDAP_BASE_DN = os.environ.get("BASTION_LDAP_BASE_DN", "")

JWT_SECRET = os.environ.get("BASTION_JWT_SECRET", "")
if not JWT_SECRET:
    # Dev-only ephemeral secret. Every restart invalidates existing sessions.
    # Production MUST set BASTION_JWT_SECRET explicitly (see SETUP.md).
    JWT_SECRET = secrets.token_urlsafe(48)
JWT_ALGORITHM = "HS256"
JWT_TTL_MINUTES = int(os.environ.get("BASTION_JWT_TTL_MINUTES", "480"))

MANIFEST_PATH = os.environ.get(
    "BASTION_MANIFEST_PATH",
    str(BACKEND_ROOT / "config" / "models_manifest.yaml"),
)
