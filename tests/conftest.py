import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for sub in ("apps/api", "apps/worker"):
    path = str(ROOT / sub)
    if path not in sys.path:
        sys.path.insert(0, path)

# Tests exercise the queue without a background worker racing them, on an isolated temp database.
_tmp = tempfile.mkdtemp(prefix="sceneseek-tests-")
os.environ["RUN_EMBEDDED_WORKER"] = "false"
os.environ["RATE_LIMIT_ENABLED"] = "false"
os.environ["DATA_DIR"] = _tmp
os.environ["DATABASE_URL"] = "sqlite:///" + (Path(_tmp) / "test.db").as_posix()
os.environ["UPLOAD_DIR"] = str(Path(_tmp) / "uploads")
os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-client.apps.googleusercontent.com")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sceneseek_project.settings")
