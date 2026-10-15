from collections.abc import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from app.config import get_settings


class Base(DeclarativeBase):
    pass


settings = get_settings()
_engine_kwargs = {"pool_pre_ping": True}
if settings.database_url_normalized.startswith("sqlite:"):
    _engine_kwargs["connect_args"] = {"check_same_thread": False, "timeout": 30}
engine: Engine = create_engine(settings.database_url_normalized, **_engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, class_=Session)


def init_db() -> None:
    # Import model declarations before create_all.
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)


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
