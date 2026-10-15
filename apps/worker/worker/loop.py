from __future__ import annotations
import asyncio
import os
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
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sceneseek_project.settings")
import django
django.setup()
from django.db import transaction
from django.utils import timezone as django_timezone
from core.models import Job

def utcnow():
    return django_timezone.now()
from app.services.media import UnsupportedMedia, dedupe_paths, extract_video_frames, prepare_image, probe_video, validate_image_bytes
from app.services.storage import cleanup_local_uploads, delete_upload, read_upload
from worker.pipeline.recognize import recognize

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
    with transaction.atomic():
        stale_jobs = list(Job.objects.select_for_update(skip_locked=True).filter(
            status="processing", started_at__lt=cutoff
        ))
        for job in stale_jobs:
            if job.attempts < job.max_attempts:
                job.status = "queued"
                job.error = "Worker lease expired; retrying the job."
            else:
                job.status = "failed"
                job.error = "Worker stopped before the job could finish. Please upload again."
                job.finished_at = utcnow()
            job.started_at = None
            job.save(update_fields=["status", "error", "finished_at", "started_at"])
            recovered += 1
    return recovered


def _claim_one() -> dict[str, Any] | None:
    """Claim a queue item transactionally; PostgreSQL supports SKIP LOCKED."""
    with transaction.atomic():
        job = Job.objects.select_for_update(skip_locked=True).filter(
            status="queued"
        ).order_by("created_at").first()
        if not job:
            return None
        job.status = "processing"
        job.attempts += 1
        job.started_at = utcnow()
        job.error = None
        job.latency_ms = None
        job.save(update_fields=["status", "attempts", "started_at", "error", "latency_ms"])
        return {"id": job.id, "input_kind": job.input_kind, "input_path": job.input_path,
                "mime": job.mime, "created_at": job.created_at}


def _save_progress(job_id: str, progress_note: str | None = None) -> None:
    # Touch started_at as a lease heartbeat. Progress is logged rather than exposed as false precision.
    Job.objects.filter(pk=job_id, status="processing").update(started_at=utcnow())
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
        job = Job.objects.filter(pk=job_id).first()
        if not job:
            delete_upload(snapshot.get("input_path"))
            return True
        job.result = result
        job.status = "done"
        job.error = None
        job.input_path = None
        job.finished_at = utcnow()
        job.latency_ms = result["latency_ms"]
        job.save(update_fields=["result", "status", "error", "input_path", "finished_at", "latency_ms"])
        delete_upload(snapshot.get("input_path"))
        logger.info("Job completed", extra={"job_id": job_id, "latency_ms": result["latency_ms"]})
    except UnsupportedMedia as exc:
        job = Job.objects.filter(pk=job_id).first()
        if job:
            job.status = "failed"
            job.error = str(exc)
            job.input_path = None
            job.finished_at = utcnow()
            job.latency_ms = int((time.perf_counter() - start) * 1000)
            job.save(update_fields=["status", "error", "input_path", "finished_at", "latency_ms"])
        delete_upload(snapshot.get("input_path"))
        logger.warning("Job rejected by media validation", extra={"job_id": job_id})
    except Exception as exc:
        logger.exception("Job processing failed", extra={"job_id": job_id})
        terminal = False
        job = Job.objects.filter(pk=job_id).first()
        if job:
            terminal = job.attempts >= job.max_attempts
            job.status = "failed" if terminal else "queued"
            job.error = "Recognition failed after retries. Please try again." if terminal else "Temporary processing issue; the job will retry."
            update_fields = ["status", "error"]
            if terminal:
                job.input_path = None
                job.finished_at = utcnow()
                update_fields += ["input_path", "finished_at"]
            else:
                job.started_at = None
                update_fields.append("started_at")
            job.save(update_fields=update_fields)
        if terminal:
            delete_upload(snapshot.get("input_path"))
    finally:
        _write_heartbeat("idle", queue_checked_at=datetime.now(timezone.utc).isoformat())
    return True


def _tick(cleanup_due: bool) -> bool:
    """One unit of work, always executed on the same thread so DB connections are reused and closed properly."""
    from django.db import close_old_connections
    close_old_connections()
    try:
        recover_expired_jobs()
        worked = process_one()
        if cleanup_due:
            cleanup_local_uploads(get_settings().upload_ttl_hours * 3600)
        return worked
    finally:
        close_old_connections()


async def serve() -> None:
    from concurrent.futures import ThreadPoolExecutor
    settings = get_settings()
    logger.info("SceneSeek worker started")
    _write_heartbeat("idle")
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sceneseek-job")
    loop = asyncio.get_running_loop()
    last_cleanup = 0.0
    failures = 0
    try:
        while True:
            try:
                now = time.monotonic()
                due = now - last_cleanup > 3600
                worked = await loop.run_in_executor(executor, _tick, due)
                if due:
                    last_cleanup = now
                failures = 0
                if not worked:
                    await asyncio.sleep(settings.worker_poll_seconds)
            except asyncio.CancelledError:
                _write_heartbeat("stopping")
                raise
            except Exception:
                failures += 1
                logger.exception("Worker loop error")
                _write_heartbeat("degraded")
                # Back off (max 30 s) so a sleeping Neon database or an outage is not hammered.
                await asyncio.sleep(min(30.0, max(settings.worker_poll_seconds, 3.0) * failures))
    finally:
        executor.shutdown(wait=False)


def main() -> None:
    logging.basicConfig(level=get_settings().log_level.upper(), format="%(asctime)s %(levelname)s %(name)s %(message)s")
    asyncio.run(serve())


if __name__ == "__main__":
    main()
