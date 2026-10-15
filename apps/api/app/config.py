from functools import lru_cache
from pathlib import Path
from pydantic import field_validator
from app import env
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(str(env.REPO_ROOT / ".env"), str(env.API_DIR / ".env")), env_file_encoding="utf-8", extra="ignore", env_ignore_empty=True)

    app_env: str = "development"
    app_name: str = "SceneSeek API"
    frontend_url: str = ""
    log_level: str = "INFO"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    api_rate_limit_per_minute: int = 10
    read_rate_limit_per_minute: int = 180
    database_url: str = env.DEFAULT_DATABASE_URL
    upload_dir: str = str(env.DATA_DIR / "uploads")
    max_image_bytes: int = 10 * 1024 * 1024
    max_video_bytes: int = 25 * 1024 * 1024
    max_video_seconds: int = 30
    upload_ttl_hours: int = 24
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_bucket: str = "uploads"
    reference_index_path: str = str(env.DATA_DIR / "reference" / "index.json")
    evaluation_report_path: str = str(env.REPORTS_DIR / "evaluation.json")
    worker_status_path: str = str(env.DATA_DIR / "worker_status.json")
    worker_poll_seconds: float = 2.0
    job_lease_seconds: int = 180
    omdb_api_key: str = ""
    enable_ocr: bool = False
    enable_asr: bool = False
    enable_online_anime: bool = True
    # Render free has no background-worker tier: run the queue worker inside the API process.
    run_embedded_worker: bool = True
    # Google sign-in (optional). Create an OAuth *Web* client at console.cloud.google.com (free).
    google_client_id: str = ""
    jwt_secret: str = ""
    jwt_ttl_hours: int = 24 * 7
    require_login: bool = False
    clip_model: str = "clip-ViT-B-32"
    use_pgvector: bool = False
    metadata_enrichment_enabled: bool = True
    metadata_cache_hours: int = 24

    @field_validator("api_rate_limit_per_minute", "read_rate_limit_per_minute")
    @classmethod
    def positive_rate_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Rate limits must be positive")
        return value

    @field_validator("database_url")
    @classmethod
    def usable_database_url(cls, value: str) -> str:
        return env.normalize_database_url(value)

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip().rstrip("/") for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def database_url_normalized(self) -> str:
        # Cloud providers frequently provide postgres:// rather than SQLAlchemy's URL.
        url = self.database_url
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url.removeprefix("postgres://")
        if url.startswith("postgresql://") and "+psycopg" not in url:
            return url.replace("postgresql://", "postgresql+psycopg://", 1)
        return url

    def ensure_local_dirs(self) -> None:
        db_file = env.sqlite_path_from_url(self.database_url_normalized)
        if db_file:
            env.ensure_dirs(Path(db_file).parent)
        env.ensure_dirs(self.upload_dir, Path(self.reference_index_path).parent, Path(self.worker_status_path).parent)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_local_dirs()
    return settings
