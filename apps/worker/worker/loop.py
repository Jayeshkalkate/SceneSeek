from __future__ import annotations
import asyncio
import json
import logging
import mimetypes
import shutil
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from app.config import get_settings
from app.database import SessionLocal, init_db
from app.models import Job, utcnow
from app.services.media import UnsupportedMedia, dedupe_paths, extract_video_frames, prepare_image, probe_video, validate_image_bytes
from app.services.storage import cleanup_local_uploads, delete_upload, read_upload
from worker.pipeline.recognize import recognize
from sqlalchemy import select

logger = logging.getLogger("sceneseek.worker")


def _write_heartbeat(state: str, **extra: Any) -> None:
    settings = get_settings()
    path = Path(settings.worker_status_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"status": state, "updated_at": datetime.now(timezone.utc).isoformat(), **extra}
    temp_path = path.with_suffix(path.suffix + ".tmp")
    try:
        temp_path.write_text(json.dumps(payload), encoding="utf-8")
        temp_path.replace(path)
    except OSError:
        logger.warning("Could not write worker heartbeat")


def recover_expired_jobs() -> int:
    settings = get_settings()
    cutoff = utcnow() - timedelta(seconds=max(60, settings.job_lease_seconds))
    recovered = 0
    with SessionLocal() as db:
        stale_jobs = db.scalars(select(Job).where(Job.status == "processing", Job.started_at < cutoff)).all()
        for job in stale_jobs:
            if job.attempts < job.max_attempts:
                job.status = "queued"
                job.error = "Worker lease expired; retrying the job."
            else:
                job.status = "failed"
                job.error = "Worker stopped before the job could finish. Please upload again."
                job.finished_at = utcnow()
            job.started_at = None
            recovered += 1
        if recovered:
            db.commit()
    return recovered


def _claim_one() -> dict[str, Any] | None:
    """Postgres uses SKIP LOCKED; the status predicate also protects SQLite single-worker dev."""
    with SessionLocal() as db:
        with db.begin():
            stmt = select(Job).where(Job.status == "queued").order_by(Job.created_at).limit(1).with_for_update(skip_locked=True)
            job = db.scalar(stmt)
            if not job:
                return None
            job.status = "processing"
            job.attempts += 1
            job.started_at = utcnow()
            job.error = None
            job.latency_ms = None
            snapshot = {"id": job.id, "input_kind": job.input_kind, "input_path": job.input_path,
                        "mime": job.mime, "created_at": job.created_at}
        return snapshot


def _save_progress(job_id: str, progress_note: str | None = None) -> None:
    # Touch started_at as a lease heartbeat. Progress is logged rather than exposed as false precision.
    with SessionLocal() as db:
        job = db.get(Job, job_id)
        if job and job.status == "processing":
            job.started_at = utcnow()
            db.commit()
    if progress_note:
        logger.info(progress_note, extra={"job_id": job_id})


def _extension(mime: str) -> str:
    return {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp",
            "video/mp4": ".mp4", "application/mp4": ".mp4", "video/webm": ".webm",
            "video/quicktime": ".mov"}.get(mime, ".bin")


def _run_pipeline(snapshot: dict[str, Any]) -> dict[str, Any]:
    job_id = snapshot["id"]
    settings = get_settings()
    uri = snapshot.get("input_path")
    if not uri:
        raise UnsupportedMedia("The upload has expired. Please upload it again.")
    with tempfile.TemporaryDirectory(prefix=f"sceneseek-{job_id[:8]}-") as temp:
        root = Path(temp)
        input_path = root / f"input{_extension(snapshot['mime'])}"
        try:
            data = read_upload(uri)
        except Exception as exc:
            raise RuntimeError("Could not retrieve the uploaded file. It may have expired.") from exc
        input_path.write_bytes(data)
        frames_dir = root / "frames"
        frames_dir.mkdir()
        video_path = None
        if snapshot["input_kind"] == "image":
            validate_image_bytes(data)
            image = prepare_image(input_path, max_width=1024)
            frame = frames_dir / "frame_001.jpg"
            image.save(frame, format="JPEG", quality=92, optimize=True)
            image.close()
            raw_frames = [frame]
        else:
            video_info = probe_video(input_path, settings.max_video_seconds)
            video_path = input_path
            _save_progress(job_id, "Video validated; extracting frames")
            raw_frames = extract_video_frames(input_path, frames_dir, video_info["duration"])
        frames = dedupe_paths(raw_frames)
        if not frames:
            raise UnsupportedMedia("No usable frames were found. Please try a clearer file.")
        _save_progress(job_id, f"Processing {len(frames)} frame(s)")
        result = recognize(frames, root, video_path=video_path)
        return result


def process_one() -> bool:
    snapshot = _claim_one()
    if not snapshot:
        return False
    job_id = snapshot["id"]
    start = time.perf_counter()
    _write_heartbeat("busy", job_id=job_id)
    try:
        result = _run_pipeline(snapshot)
        result["latency_ms"] = int((time.perf_counter() - start) * 1000)
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if not job:
                delete_upload(snapshot.get("input_path"))
                return True
            job.result = result
            job.status = "done"
            job.error = None
            job.input_path = None
            job.finished_at = utcnow()
            job.latency_ms = result["latency_ms"]
            db.commit()
        delete_upload(snapshot.get("input_path"))
        logger.info("Job completed", extra={"job_id": job_id, "latency_ms": result["latency_ms"]})
    except UnsupportedMedia as exc:
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                job.status = "failed"
                job.error = str(exc)
                job.input_path = None
                job.finished_at = utcnow()
                job.latency_ms = int((time.perf_counter() - start) * 1000)
                db.commit()
        delete_upload(snapshot.get("input_path"))
        logger.warning("Job rejected by media validation", extra={"job_id": job_id})
    except Exception as exc:
        logger.exception("Job processing failed", extra={"job_id": job_id})
        terminal = False
        with SessionLocal() as db:
            job = db.get(Job, job_id)
            if job:
                terminal = job.attempts >= job.max_attempts
                job.status = "failed" if terminal else "queued"
                job.error = "Recognition failed after retries. Please try again." if terminal else "Temporary processing issue; the job will retry."
                if terminal:
                    job.input_path = None
                    job.finished_at = utcnow()
                else:
                    job.started_at = None
                db.commit()
        if terminal:
            delete_upload(snapshot.get("input_path"))
    finally:
        _write_heartbeat("idle", queue_checked_at=datetime.now(timezone.utc).isoformat())
    return True


async def serve() -> None:
    init_db()
    settings = get_settings()
    logger.info("SceneSeek worker started")
    _write_heartbeat("idle")
    last_cleanup = 0.0
    while True:
        try:
            await asyncio.to_thread(recover_expired_jobs)
            worked = await asyncio.to_thread(process_one)
            now = time.monotonic()
            if now - last_cleanup > 3600:
                await asyncio.to_thread(cleanup_local_uploads, settings.upload_ttl_hours * 3600)
                last_cleanup = now
            if not worked:
                await asyncio.sleep(settings.worker_poll_seconds)
        except asyncio.CancelledError:
            _write_heartbeat("stopping")
            raise
        except Exception:
            logger.exception("Worker loop error")
            _write_heartbeat("degraded")
            await asyncio.sleep(max(settings.worker_poll_seconds, 3.0))


def main() -> None:
    logging.basicConfig(level=get_settings().log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(serve())


if __name__ == "__main__":
    main()
