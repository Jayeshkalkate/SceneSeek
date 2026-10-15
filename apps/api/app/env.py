"""Shared environment/path bootstrap for Django, the worker, tools and tests.

Importing this module (a) loads ``.env`` files, (b) drops blank or placeholder
values so sane defaults apply, and (c) exposes absolute default paths that work
on Windows, macOS, Linux and Docker alike (no hard-coded ``/data``).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

API_DIR = Path(__file__).resolve().parents[1]
# <repo>/apps/api -> <repo>. In Docker the code lives in /app, so fall back to API_DIR.
REPO_ROOT = API_DIR.parent.parent if API_DIR.parent.name == "apps" else API_DIR
WORKER_DIR = (REPO_ROOT / "apps" / "worker") if (REPO_ROOT / "apps" / "worker").is_dir() else (API_DIR / "worker")

try:  # python-dotenv is a declared dependency, but never crash if it is missing.
    from dotenv import load_dotenv

    for _candidate in (REPO_ROOT / ".env", API_DIR / ".env"):
        if _candidate.is_file():
            load_dotenv(_candidate, override=False)
except ImportError:  # pragma: no cover
    pass

# Blank values (``KEY=``) in .env must behave like "unset".
_BLANK_MEANS_DEFAULT = (
    "DATABASE_URL", "UPLOAD_DIR", "REFERENCE_INDEX_PATH", "EVALUATION_REPORT_PATH",
    "WORKER_STATUS_PATH", "DATA_DIR", "DJANGO_SECRET_KEY", "JWT_SECRET", "ALLOWED_HOSTS", "CORS_ORIGINS",
)
for _key in _BLANK_MEANS_DEFAULT:
    if not os.environ.get(_key, "").strip():
        os.environ.pop(_key, None)

DATA_DIR = Path(os.environ.get("DATA_DIR") or (REPO_ROOT / "data")).expanduser()
REPORTS_DIR = Path(os.environ.get("REPORTS_DIR") or (REPO_ROOT / "reports")).expanduser()
DEFAULT_DATABASE_URL = "sqlite:///" + (DATA_DIR / "sceneseek.db").as_posix()

# A copied .env.example contains this placeholder; it can never connect, so ignore it.
_PLACEHOLDER_MARKERS = ("USER:PASSWORD@HOST", "@HOST/", "YOUR_PASSWORD")


def normalize_database_url(url: str | None) -> str:
    """Return a usable database URL; relative SQLite paths become absolute (anchored at the repo root)."""
    url = (url or "").strip()
    if not url or any(marker in url for marker in _PLACEHOLDER_MARKERS):
        return DEFAULT_DATABASE_URL
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////") and ":memory:" not in url:
        raw = url[len("sqlite:///"):]
        is_windows_abs = len(raw) > 1 and raw[1] == ":"
        if raw and not is_windows_abs and not Path(raw).is_absolute():
            return "sqlite:///" + (REPO_ROOT / raw).resolve().as_posix()
    return url


def sqlite_path_from_url(url: str) -> str | None:
    """Filesystem path for a sqlite URL, or None for other engines / in-memory databases."""
    if not url.startswith("sqlite:///"):
        return None
    raw = url[len("sqlite:///"):]
    if not raw or raw == ":memory:" or raw.startswith("file:"):
        return None
    # ``sqlite:////abs/path`` leaves a leading slash we must keep; ``sqlite:///C:/x`` has none.
    return raw


def ensure_importable_paths() -> None:
    """Make ``app`` (API) and ``worker`` (apps/worker) importable regardless of the current directory."""
    for path in (API_DIR, WORKER_DIR):
        text = str(path)
        if path.is_dir() and text not in sys.path:
            sys.path.insert(0, text)


def ensure_dirs(*paths: str | os.PathLike[str]) -> None:
    for path in paths:
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
        except OSError:  # read-only filesystems are handled where the path is used
            pass


ensure_importable_paths()
