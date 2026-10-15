from __future__ import annotations
import hashlib
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
from fastapi import Depends, FastAPI, File, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import db_is_healthy, get_db, init_db
from app.models import Feedback, Job, MetadataCache, TakedownRequest
from app.schemas import FeedbackCreate, FeedbackResponse, IdentificationResult, JobAccepted, JobStatus, TakedownCreate
from app.security import RateLimitMiddleware, UploadBodyLimitMiddleware
from app.services.media import UnsupportedMedia, detect_kind, sha256_bytes, validate_image_bytes
from app.services.metadata import enrich_metadata, search_titles
from app.services.reference_index import get_title, load_index
from app.services.storage import StorageError, delete_upload, store_upload


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {"time": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                   "logger": record.name, "message": record.getMessage()}
        for key in ("job_id", "request_id", "path", "status_code", "latency_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, ensure_ascii=False)


_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
_root_logger = logging.getLogger()
if not _root_logger.handlers:
    _root_logger.addHandler(_handler)
_root_logger.setLevel(getattr(logging, get_settings().log_level.upper(), logging.INFO))
logger = logging.getLogger("sceneseek.api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    logger.info("SceneSeek API starting", extra={"path": "/startup"})
    yield
    logger.info("SceneSeek API stopping", extra={"path": "/shutdown"})


settings = get_settings()
app = FastAPI(
    title="SceneSeek API", version="1.0.0",
    description="Upload-first entertainment visual search. A prepared, lawfully sourced reference index is required for recognition.",
    lifespan=lifespan,
)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(UploadBodyLimitMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _job_status(job: Job) -> JobStatus:
    progress = {"queued": 5, "processing": 60, "done": 100, "failed": 100}.get(job.status, 0)
    result = IdentificationResult.model_validate(job.result) if job.result else None
    return JobStatus(id=job.id, status=job.status, progress=progress, result=result,
                     error=job.error, created_at=job.created_at.isoformat(), finished_at=_iso(job.finished_at))


@app.get("/")
def root() -> dict:
    return {"name": "SceneSeek", "tagline": "See it. Seek it. Find it.", "docs": "/docs", "health": "/healthz"}


@app.get("/healthz")
def health(db: Session = Depends(get_db)) -> dict:
    database_ok = db_is_healthy()
    queue_depth = db.scalar(select(func.count()).select_from(Job).where(Job.status == "queued")) if database_ok else None
    index = load_index()
    worker_status = {"status": "unknown"}
    try:
        worker_status = json.loads(Path(settings.worker_status_path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {"ok": database_ok, "db": database_ok, "queue_depth": queue_depth,
            "reference_index_ready": bool(index.get("frames")), "reference_titles": len(index.get("titles", [])),
            "worker": worker_status, "storage": "supabase" if settings.supabase_url and settings.supabase_service_key else "local"}


@app.post("/v1/identify", response_model=JobAccepted, status_code=status.HTTP_202_ACCEPTED)
async def identify(file: UploadFile = File(...), db: Session = Depends(get_db)) -> JobAccepted:
    filename = (file.filename or "upload").replace("\\", "/").split("/")[-1][:180]
    mime = (file.content_type or "application/octet-stream").lower().split(";", 1)[0].strip()
    try:
        kind = detect_kind(filename, mime)
    except UnsupportedMedia as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from exc
    limit = settings.max_image_bytes if kind == "image" else settings.max_video_bytes
    data = await file.read(limit + 1)
    await file.close()
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"The file exceeds the {limit // (1024 * 1024)} MB limit.")
    if kind == "image":
        try:
            validate_image_bytes(data)
        except UnsupportedMedia as exc:
            raise HTTPException(status_code=415, detail=str(exc)) from exc

    digest = sha256_bytes(data)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    existing = db.scalar(select(Job).where(Job.sha256 == digest, Job.status.in_(["queued", "processing"]), Job.created_at >= cutoff).limit(1))
    if existing:
        return JobAccepted(job_id=existing.id, status=existing.status, poll_after_ms=1500)

    job_id = str(uuid4())
    suffix = Path(filename).suffix.lower()
    key = f"{job_id}/{uuid4().hex}{suffix}"
    try:
        stored_uri = await run_in_threadpool(store_upload, data, key, mime)
    except (StorageError, OSError, ValueError) as exc:
        logger.exception("Could not store upload", extra={"job_id": job_id})
        raise HTTPException(status_code=503, detail="Upload storage is temporarily unavailable. Please retry.") from exc

    job = Job(id=job_id, status="queued", input_kind=kind, input_path=stored_uri, mime=mime,
              bytes=len(data), sha256=digest, attempts=0, max_attempts=3)
    try:
        db.add(job)
        db.commit()
    except Exception as exc:
        db.rollback()
        delete_upload(stored_uri)
        logger.exception("Could not enqueue job", extra={"job_id": job_id})
        raise HTTPException(status_code=503, detail="The job queue is temporarily unavailable.") from exc
    logger.info("Upload accepted", extra={"job_id": job_id, "path": "/v1/identify"})
    return JobAccepted(job_id=job_id, status="queued", poll_after_ms=1500)


@app.get("/v1/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str, db: Session = Depends(get_db)) -> JobStatus:
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired.")
    return _job_status(job)


@app.post("/v1/feedback", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
def submit_feedback(payload: FeedbackCreate, db: Session = Depends(get_db)) -> FeedbackResponse:
    job = db.get(Job, payload.job_id)
    if not job:
        raise HTTPException(status_code=404, detail="The referenced job was not found.")
    feedback = Feedback(job_id=payload.job_id, predicted_title_id=payload.predicted_title_id,
                        correct_title_id=payload.correct_title_id, verdict=payload.verdict,
                        note=payload.note.strip() if payload.note else None)
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return FeedbackResponse(id=feedback.id)


@app.get("/v1/titles/{title_id}")
def title_detail(title_id: str, db: Session = Depends(get_db)) -> dict:
    title = get_title(title_id)
    if not title and title_id.startswith("anilist-") and title_id.removeprefix("anilist-").isdigit():
        from app.services.metadata import anilist_by_id
        found = anilist_by_id(int(title_id.removeprefix("anilist-")))
        if found:
            return {**found, "title_id": title_id, "kind": "anime"}
    if not title:
        raise HTTPException(status_code=404, detail="Title not found in the current reference index.")
    if not settings.metadata_enrichment_enabled:
        return title
    cache = db.get(MetadataCache, title_id)
    now = datetime.now(timezone.utc)
    if cache and cache.fetched_at:
        fetched_at = cache.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=timezone.utc)
        if now - fetched_at < timedelta(hours=max(1, settings.metadata_cache_hours)):
            return cache.data
    enriched = enrich_metadata(title)
    try:
        if cache:
            cache.data = enriched
            cache.fetched_at = now
        else:
            db.add(MetadataCache(title_id=title_id, data=enriched, fetched_at=now))
        db.commit()
    except Exception:
        db.rollback()
        logger.warning("Metadata cache could not be updated", extra={"path": f"/v1/titles/{title_id}"})
    return enriched


@app.get("/v1/stats/accuracy")
def accuracy_stats(db: Session = Depends(get_db)) -> dict:
    report = None
    try:
        path = Path(settings.evaluation_report_path)
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Evaluation report could not be read")
    feedback_count = db.scalar(select(func.count()).select_from(Feedback)) or 0
    verdict_counts = {verdict: (db.scalar(select(func.count()).select_from(Feedback).where(Feedback.verdict == verdict)) or 0)
                      for verdict in ("correct", "wrong", "unknown")}
    return {"evaluation_available": report is not None, "evaluation": report,
            "feedback_count": feedback_count, "feedback_verdicts": verdict_counts,
            "disclaimer": "Accuracy is not claimed until a labeled evaluation set has been run." if report is None else "Metrics are from the labeled fixture set, not a guarantee for arbitrary uploads."}


@app.post("/v1/takedown", status_code=status.HTTP_202_ACCEPTED)
def submit_takedown(payload: TakedownCreate, db: Session = Depends(get_db)) -> dict:
    request_record = TakedownRequest(source_url=str(payload.source_url), reason=payload.reason,
                                     contact_email=payload.contact_email)
    db.add(request_record)
    db.commit()
    db.refresh(request_record)
    return {"id": request_record.id, "status": "received", "message": "The removal request has been recorded for review."}


@app.get("/v1/search")
async def search(q: str = Query(min_length=2, max_length=120)) -> dict:
    """Text title lookup (free public sources). Complements, never replaces, visual matching."""
    results = await run_in_threadpool(search_titles, q)
    return {"query": q, "results": results}


@app.get("/v1/reference/status")
def reference_status() -> dict:
    index = load_index()
    return {"ready": bool(index.get("frames")), "algorithm": index.get("algorithm", "unknown"),
            "titles": len(index.get("titles", [])), "frames": len(index.get("frames", [])),
            "index_version": index.get("version", 1)}
