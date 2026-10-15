"""Django settings for SceneSeek.

Everything is driven by environment variables (see ``.env.example``). With *no*
configuration at all the project runs locally on SQLite stored in ``<repo>/data``.
"""
import logging
import os
from pathlib import Path

import dj_database_url
from django.core.exceptions import ImproperlyConfigured

from app import env  # noqa: F401  (loads .env, fixes sys.path, provides default paths)
from app.env import (DATA_DIR, REPORTS_DIR, REPO_ROOT, ensure_dirs, normalize_database_url,
                     sqlite_path_from_url)

BASE_DIR = Path(__file__).resolve().parents[1]


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name, "").strip().lower()
    return default if not raw else raw in {"1", "true", "yes", "on"}  # blank == unset


def _int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.getenv(name, "").strip()
    try:
        return max(minimum, int(raw)) if raw else default
    except ValueError:
        return default


def _list(name: str, default: str) -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


APP_ENV = os.getenv("APP_ENV", "development").lower()
PRODUCTION = APP_ENV == "production"
DEBUG = _bool("DJANGO_DEBUG", False)
_DEV_SECRET = "dev-only-change-me"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or os.getenv("JWT_SECRET") or _DEV_SECRET
ALLOWED_HOSTS = _list("ALLOWED_HOSTS", "*")
ROOT_URLCONF = "sceneseek_project.urls"
WSGI_APPLICATION = "sceneseek_project.wsgi.application"
ASGI_APPLICATION = "sceneseek_project.asgi.application"

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "core",
]
MIDDLEWARE = [
    # Outermost so that *every* response (including 429/500) carries request-id + CORS headers.
    "core.middleware.RequestIdMiddleware",
    "core.middleware.CorsMiddleware",
    "core.middleware.RateLimitMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [], "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

# ---------------------------------------------------------------- database
DATABASE_URL = normalize_database_url(os.getenv("DATABASE_URL"))
_sqlite_file = sqlite_path_from_url(DATABASE_URL)
if _sqlite_file or DATABASE_URL.startswith("sqlite:///:memory:"):
    if _sqlite_file:
        ensure_dirs(Path(_sqlite_file).parent)  # fixes "unable to open database file"
    DATABASES = {"default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _sqlite_file or ":memory:",
        "OPTIONS": {"timeout": 30},
    }}
else:
    DATABASES = {"default": dj_database_url.parse(
        DATABASE_URL, conn_max_age=_int("DB_CONN_MAX_AGE", 60), conn_health_checks=True)}
    if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
        options = DATABASES["default"].setdefault("OPTIONS", {})
        if "sslmode=" not in DATABASE_URL:
            options.setdefault("sslmode", os.getenv("DB_SSLMODE", "require"))
        options.setdefault("connect_timeout", 20)   # Neon free computes need a moment to wake up
        options.setdefault("prepare_threshold", None)  # safe with Neon's PgBouncer pooler
        DATABASES["default"]["DISABLE_SERVER_SIDE_CURSORS"] = True

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------- app settings
CORS_ORIGINS = [x.rstrip("/") for x in _list("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")]
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET") or SECRET_KEY
JWT_TTL_HOURS = _int("JWT_TTL_HOURS", 168, 1)
REQUIRE_LOGIN = _bool("REQUIRE_LOGIN", False)
MAX_IMAGE_BYTES = _int("MAX_IMAGE_BYTES", 10 * 1024 * 1024, 1024)
MAX_VIDEO_BYTES = _int("MAX_VIDEO_BYTES", 25 * 1024 * 1024, 1024)
MAX_VIDEO_SECONDS = _int("MAX_VIDEO_SECONDS", 30, 1)
DATA_UPLOAD_MAX_MEMORY_SIZE = max(MAX_IMAGE_BYTES, MAX_VIDEO_BYTES) + 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 2 * 1024 * 1024  # larger files stream to a temp file, not RAM
UPLOAD_DIR = os.getenv("UPLOAD_DIR") or str(DATA_DIR / "uploads")
REFERENCE_INDEX_PATH = os.getenv("REFERENCE_INDEX_PATH") or str(DATA_DIR / "reference" / "index.json")
EVALUATION_REPORT_PATH = os.getenv("EVALUATION_REPORT_PATH") or str(REPORTS_DIR / "evaluation.json")
WORKER_STATUS_PATH = os.getenv("WORKER_STATUS_PATH") or str(DATA_DIR / "worker_status.json")
ensure_dirs(UPLOAD_DIR, Path(REFERENCE_INDEX_PATH).parent, Path(WORKER_STATUS_PATH).parent)
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")
METADATA_ENRICHMENT_ENABLED = _bool("METADATA_ENRICHMENT_ENABLED", True)
METADATA_CACHE_HOURS = _int("METADATA_CACHE_HOURS", 24, 1)
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
ENABLE_ONLINE_ANIME = _bool("ENABLE_ONLINE_ANIME", True)
API_RATE_LIMIT_PER_MINUTE = _int("API_RATE_LIMIT_PER_MINUTE", 10, 1)
READ_RATE_LIMIT_PER_MINUTE = _int("READ_RATE_LIMIT_PER_MINUTE", 180, 1)
RATE_LIMIT_ENABLED = _bool("RATE_LIMIT_ENABLED", True)
TRUST_PROXY_HEADERS = _bool("TRUST_PROXY_HEADERS", True)  # Render/Docker proxies set X-Forwarded-For
HISTORY_LIMIT = _int("HISTORY_LIMIT", 50, 1)
# On SQLite (single-machine local dev) the worker runs inside the API process unless told otherwise.
RUN_EMBEDDED_WORKER = _bool("RUN_EMBEDDED_WORKER", bool(_sqlite_file))

# ---------------------------------------------------------------- security
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = PRODUCTION
CSRF_COOKIE_SECURE = PRODUCTION
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

if SECRET_KEY == _DEV_SECRET:
    if PRODUCTION or GOOGLE_CLIENT_ID:
        raise ImproperlyConfigured(
            "Set DJANGO_SECRET_KEY (and JWT_SECRET) to long random values before enabling "
            "production mode or Google sign-in. Generate one with: python -c \"import secrets;print(secrets.token_hex(32))\"")
    logging.getLogger("sceneseek.django").warning("Using the built-in development secret key; set DJANGO_SECRET_KEY.")

# ---------------------------------------------------------------- logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {"django.server": {"level": "INFO"}, "django.db.backends": {"level": "WARNING"}},
}
REST_FRAMEWORK = {"UNAUTHENTICATED_USER": None}
