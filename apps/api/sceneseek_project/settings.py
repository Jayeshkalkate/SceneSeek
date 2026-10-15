import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parents[1]
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY") or os.getenv("JWT_SECRET") or "dev-only-change-me"
DEBUG = os.getenv("DJANGO_DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = [x.strip() for x in os.getenv("ALLOWED_HOSTS", "*").split(",") if x.strip()]
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
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "core.middleware.CorsMiddleware",
]
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/sceneseek.db")
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)
DATABASES = {"default": dj_database_url.parse(
    DATABASE_URL,
    conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "60")),
    conn_health_checks=True,
)}
if DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"].setdefault("sslmode", os.getenv("DB_SSLMODE", "require"))
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
CORS_ORIGINS = [x.strip().rstrip("/") for x in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if x.strip()]
FRONTEND_URL = os.getenv("FRONTEND_URL", "")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
JWT_SECRET = os.getenv("JWT_SECRET", SECRET_KEY)
JWT_TTL_HOURS = int(os.getenv("JWT_TTL_HOURS", "168"))
REQUIRE_LOGIN = os.getenv("REQUIRE_LOGIN", "false").lower() == "true"
MAX_IMAGE_BYTES = int(os.getenv("MAX_IMAGE_BYTES", str(10 * 1024 * 1024)))
MAX_VIDEO_BYTES = int(os.getenv("MAX_VIDEO_BYTES", str(25 * 1024 * 1024)))
MAX_VIDEO_SECONDS = int(os.getenv("MAX_VIDEO_SECONDS", "30"))
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "/data/uploads")
REFERENCE_INDEX_PATH = os.getenv("REFERENCE_INDEX_PATH", "/data/reference/index.json")
EVALUATION_REPORT_PATH = os.getenv("EVALUATION_REPORT_PATH", "/data/reports/evaluation.json")
WORKER_STATUS_PATH = os.getenv("WORKER_STATUS_PATH", "/data/worker_status.json")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY", "")
SUPABASE_BUCKET = os.getenv("SUPABASE_BUCKET", "uploads")
METADATA_ENRICHMENT_ENABLED = os.getenv("METADATA_ENRICHMENT_ENABLED", "true").lower() == "true"
METADATA_CACHE_HOURS = int(os.getenv("METADATA_CACHE_HOURS", "24"))
OMDB_API_KEY = os.getenv("OMDB_API_KEY", "")
ENABLE_ONLINE_ANIME = os.getenv("ENABLE_ONLINE_ANIME", "true").lower() == "true"
API_RATE_LIMIT_PER_MINUTE = int(os.getenv("API_RATE_LIMIT_PER_MINUTE", "10"))
READ_RATE_LIMIT_PER_MINUTE = int(os.getenv("READ_RATE_LIMIT_PER_MINUTE", "180"))
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
