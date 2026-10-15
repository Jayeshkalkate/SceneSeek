from collections.abc import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
_engine_kwargs: dict = {"pool_pre_ping": True}
if settings.database_url_normalized.startswith("sqlite:"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
else:
    # Neon free: compute auto-suspends when idle and the pooled endpoint is PgBouncer.
    # Recycle connections often, keep the pool small, wait for cold starts, avoid prepared statements.
    _engine_kwargs.update(pool_size=3, max_overflow=2, pool_recycle=240, pool_timeout=30)
    _engine_kwargs["connect_args"] = {"connect_timeout": 20, "prepare_threshold": None}
engine: Engine = create_engine(settings.database_url_normalized, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_db() -> None:
    # Import model declarations before create_all.
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)
    _ensure_columns()


def _ensure_columns() -> None:
    """Add columns introduced after the first deploy (create_all never alters existing tables)."""
    try:
        with engine.begin() as conn:
            if engine.dialect.name == "sqlite":
                cols = {row[1] for row in conn.execute(text("PRAGMA table_info(jobs)"))}
                if "user_id" not in cols:
                    conn.execute(text("ALTER TABLE jobs ADD COLUMN user_id VARCHAR(36)"))
            else:
                conn.execute(text("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS user_id VARCHAR(36)"))
    except Exception:
        import logging
        logging.getLogger(__name__).warning("Column check skipped", exc_info=True)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def db_is_healthy() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
