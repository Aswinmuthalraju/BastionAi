import os
import tempfile

# Must run before any `app.*` module is imported by a test file, so every
# singleton (db path, qdrant path, kuzu path) initializes against an isolated
# throwaway directory instead of the real dev data in backend/data/.
_TEST_DATA_DIR = tempfile.mkdtemp(prefix="bastion_test_")
os.environ.setdefault("BASTION_DATA_DIR", _TEST_DATA_DIR)
os.environ.setdefault("BASTION_JWT_SECRET", "test-secret-do-not-use-in-production")

import sys  # noqa: E402

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db import init_db  # noqa: E402

init_db()
