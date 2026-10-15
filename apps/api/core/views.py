import base64, hashlib, hmac, json, logging, mimetypes, os, time
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Count
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseRedirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.services.media import UnsupportedMedia, detect_kind, sha256_bytes, validate_image_bytes
from app.services.metadata import enrich_metadata, search_titles
from app.services.reference_index import get_title, load_index
from app.services.storage import StorageError, delete_upload, store_upload

logger = logging.getLogger("sceneseek.django")
GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

def _json_body(request):
    try:
        value = json.loads(request.body or b"{}")
        return value if isinstance(value, dict) else None
    except (ValueError, UnicodeDecodeError):
        return None

def _error(message, code=400):
    return JsonResponse({"detail": message}, status=code)

def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _token(user_id):
    if not settings.JWT_SECRET:
        raise RuntimeError("JWT_SECRET is not configured")
    body = _b64(json.dumps({"sub": user_id, "exp": int(time.time() + settings.JWT_TTL_HOURS * 3600)}, separators=(",", ":")).encode())
    sig = _b64(hmac.new(settings.JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest())
    return f"{body}.{sig}"

def _user_from_request(request):
    header = request.headers.get("Authorization", "")
    if not header.lower().startswith("bearer "):
        return None
    try:
        body, sig = header[7:].strip().split(".", 1)
        expected = _b64(hmac.new(settings.JWT_SECRET.encode(), body.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(sig, expected):
            return None
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        if int(data["exp"]) <= time.time():
            return None
        from core.models import User
        return User.objects.filter(pk=str(data["sub"])).first()
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None

def _require_user(request):
    user = _user_from_request(request)
    return user

def _user_json(user):
    return {"id": user.id, "email": user.email, "name": user.name, "picture": user.picture}

def _job_json(job):
    from core.models import Job
    progress = {"queued": 5, "processing": 60, "done": 100, "failed": 100}.get(job.status, 0)
    data = {"id": job.id, "status": job.status, "progress": progress, "result": job.result,
            "error": job.error, "created_at": job.created_at.isoformat(),
            "finished_at": job.finished_at.isoformat() if job.finished_at else None,
            "attempts": job.attempts}
    if job.status == "queued":
        data["queue_ahead"] = Job.objects.filter(status="queued", created_at__lt=job.created_at).count()
    return data


def _json_ok(payload, status=200):
    response = JsonResponse(payload, status=status)
    response["Cache-Control"] = "no-store"
    return response


def not_found(request, exception=None):
    return _error("The requested endpoint does not exist.", 404)


def server_error(request):
    return _error("Something went wrong on our side. Please try again in a moment.", 500)

@require_http_methods(["GET", "HEAD"])
def root(request):
    if settings.FRONTEND_URL.strip():
        return HttpResponseRedirect(settings.FRONTEND_URL.strip().rstrip("/"))
    return JsonResponse({"name": "SceneSeek API", "tagline": "See it. Seek it. Find it.",
                         "website": None, "docs": None, "health": "/healthz", "api": "/v1"})

@require_http_methods(["GET", "HEAD"])
def ping(request):
    return JsonResponse({"ok": True})

@require_http_methods(["GET", "HEAD"])
def health(request):
    from core.models import Job
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        queue = Job.objects.filter(status="queued").count()
    except Exception:
        db_ok, queue = False, None
    index = load_index()
    try:
        worker = json.loads(Path(settings.WORKER_STATUS_PATH).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        worker = {"status": "unknown"}
    return JsonResponse({"ok": db_ok, "db": db_ok, "queue_depth": queue,
        "reference_index_ready": bool(index.get("frames")), "reference_titles": len(index.get("titles", [])),
        "worker": worker, "storage": "supabase" if settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY else "local"})

@require_http_methods(["GET"])
def public_config(request):
    return JsonResponse({"google_login": bool(settings.GOOGLE_CLIENT_ID),
                         "google_client_id": settings.GOOGLE_CLIENT_ID, "require_login": settings.REQUIRE_LOGIN,
                         "max_image_mb": settings.MAX_IMAGE_BYTES // (1024 * 1024),
                         "max_video_mb": settings.MAX_VIDEO_BYTES // (1024 * 1024),
                         "max_video_seconds": settings.MAX_VIDEO_SECONDS,
                         "online_anime": settings.ENABLE_ONLINE_ANIME})

@csrf_exempt
@require_http_methods(["POST"])
def auth_google(request):
    from core.models import User
    payload = _json_body(request)
    credential = payload.get("credential") if payload else None
    if not credential:
        return _error("Google credential is required.")
    if not settings.GOOGLE_CLIENT_ID or not settings.JWT_SECRET:
        return _error("Google sign-in is not configured on this server.", 503)
    try:
        response = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": credential}, timeout=10)
    except httpx.HTTPError:
        return _error("Could not reach Google to verify sign-in.", 502)
    if response.status_code != 200:
        return _error("Invalid Google sign-in token.", 401)
    info = response.json()
    if info.get("aud") != settings.GOOGLE_CLIENT_ID or info.get("iss") not in GOOGLE_ISSUERS:
        return _error("Google token was issued for a different app.", 401)
    if str(info.get("email_verified")).lower() != "true" or not info.get("sub") or not info.get("email"):
        return _error("Google account email is not verified.", 401)
    user, _ = User.objects.update_or_create(google_sub=info["sub"], defaults={
        "email": info["email"], "name": info.get("name"), "picture": info.get("picture"),
        "last_login": timezone.now()})
    return JsonResponse({"token": _token(user.id), "user": _user_json(user)})

@require_http_methods(["GET"])
def me(request):
    user = _require_user(request)
    if not user:
        return _error("Please sign in with Google.", 401)
    return JsonResponse(_user_json(user))

@require_http_methods(["GET"])
def my_history(request):
    from core.models import Job
    user = _require_user(request)
    if not user:
        return _error("Please sign in with Google.", 401)
    items = []
    try:
        limit = max(1, min(int(request.GET.get("limit", "20")), settings.HISTORY_LIMIT))
    except ValueError:
        limit = 20
    for job in Job.objects.filter(user_id=user.id).order_by("-created_at")[:limit]:
        top = ((job.result or {}).get("candidates") or [None])[0]
        items.append({"job_id": job.id, "status": job.status, "created_at": job.created_at.isoformat(),
                      "title": top.get("title") if top else None, "title_id": top.get("title_id") if top else None,
                      "band": (job.result or {}).get("band")})
    return _json_ok({"items": items})

@csrf_exempt
@require_http_methods(["DELETE"])
def history_item(request, job_id):
    """Delete one of the signed-in user's past searches."""
    from core.models import Job
    user = _require_user(request)
    if not user:
        return _error("Please sign in with Google.", 401)
    job = Job.objects.filter(pk=job_id, user_id=user.id).first()
    if not job:
        return _error("That search was not found.", 404)
    delete_upload(job.input_path)
    job.delete()
    return JsonResponse({"deleted": 1})

@csrf_exempt
@require_http_methods(["DELETE"])
def history_clear(request):
    """Delete every past search of the signed-in user."""
    from core.models import Job
    user = _require_user(request)
    if not user:
        return _error("Please sign in with Google.", 401)
    jobs = Job.objects.filter(user_id=user.id)
    for job in jobs.exclude(input_path__isnull=True):
        delete_upload(job.input_path)
    deleted, _ = jobs.delete()
    return JsonResponse({"deleted": deleted})

@csrf_exempt
@require_http_methods(["DELETE"])
def delete_account(request):
    """Erase the account and everything stored for it (privacy: right to erasure)."""
    from core.models import Job, User
    user = _require_user(request)
    if not user:
        return _error("Please sign in with Google.", 401)
    for job in Job.objects.filter(user_id=user.id).exclude(input_path__isnull=True):
        delete_upload(job.input_path)
    Job.objects.filter(user_id=user.id).delete()
    User.objects.filter(pk=user.id).delete()
    return JsonResponse({"deleted": True})

@csrf_exempt
@require_http_methods(["POST"])
def identify(request):
    from core.models import Job
    user = _user_from_request(request)
    if settings.REQUIRE_LOGIN and user is None:
        return _error("Please sign in with Google to identify scenes.", 401)
    upload = request.FILES.get("file")
    if not upload:
        return _error("A file field is required.")
    filename = (upload.name or "upload").replace("\\", "/").split("/")[-1][:180]
    mime = (upload.content_type or "application/octet-stream").lower().split(";", 1)[0].strip()
    try:
        kind = detect_kind(filename, mime)
    except UnsupportedMedia as exc:
        return _error(str(exc), 415)
    limit = settings.MAX_IMAGE_BYTES if kind == "image" else settings.MAX_VIDEO_BYTES
    data = upload.read(limit + 1)
    if not data:
        return _error("The uploaded file is empty.")
    if len(data) > limit:
        return _error(f"The file exceeds the {limit // (1024 * 1024)} MB limit.", 413)
    if kind == "image":
        try:
            validate_image_bytes(data)
        except UnsupportedMedia as exc:
            return _error(str(exc), 415)
    digest = sha256_bytes(data)
    cutoff = timezone.now() - timedelta(minutes=10)
    existing = Job.objects.filter(sha256=digest, user_id=user.id if user else None,
                                  status__in=["queued", "processing"], created_at__gte=cutoff).first()
    if existing:
        return JsonResponse({"job_id": existing.id, "status": existing.status, "poll_after_ms": 1500}, status=202)
    job_id = str(uuid4())
    suffix = Path(filename).suffix.lower()
    key = f"{job_id}/{uuid4().hex}{suffix}"
    try:
        stored_uri = store_upload(data, key, mime)
    except (StorageError, OSError, ValueError):
        logger.exception("Could not store upload")
        return _error("Upload storage is temporarily unavailable. Please retry.", 503)
    try:
        with transaction.atomic():
            job = Job.objects.create(id=job_id, status="queued", input_kind=kind, input_path=stored_uri,
                mime=mime, bytes=len(data), sha256=digest, attempts=0, max_attempts=3,
                user_id=user.id if user else None)
    except Exception:
        delete_upload(stored_uri)
        logger.exception("Could not enqueue job")
        return _error("The job queue is temporarily unavailable.", 503)
    return JsonResponse({"job_id": job.id, "status": job.status, "poll_after_ms": 1500}, status=202)

@require_http_methods(["GET"])
def get_job(request, job_id):
    from core.models import Job
    job = Job.objects.filter(pk=job_id).first()
    if not job:
        return _error("Job not found or expired.", 404)
    user = _user_from_request(request)
    if job.user_id and (user is None or user.id != job.user_id):
        return _error("Job not found or expired.", 404)
    return _json_ok(_job_json(job))

@csrf_exempt
@require_http_methods(["POST"])
def submit_feedback(request):
    from core.models import Feedback, Job
    payload = _json_body(request)
    if not payload or not payload.get("job_id") or payload.get("verdict") not in {"correct", "wrong", "unknown"}:
        return _error("job_id and a valid verdict are required.")
    for field in ("predicted_title_id", "correct_title_id"):
        value = payload.get(field)
        if value is not None and (not isinstance(value, str) or len(value) > 128):
            return _error(f"{field} must be a string of at most 128 characters.")
    if payload.get("note") is not None and (not isinstance(payload["note"], str) or len(payload["note"]) > 1000):
        return _error("note must be at most 1000 characters.")
    job = Job.objects.filter(pk=payload["job_id"]).first()
    if not job:
        return _error("The referenced job was not found.", 404)
    user = _user_from_request(request)
    if job.user_id and (user is None or user.id != job.user_id):
        return _error("Job not found or expired.", 404)
    feedback = Feedback.objects.create(job=job, predicted_title_id=payload.get("predicted_title_id"),
        correct_title_id=payload.get("correct_title_id"), verdict=payload["verdict"],
        note=(payload.get("note") or "").strip() or None)
    return JsonResponse({"id": feedback.id}, status=201)

@require_http_methods(["GET"])
def title_detail(request, title_id):
    from core.models import MetadataCache
    if len(title_id) > 128:
        return _error("Invalid title id.")
    title = get_title(title_id)
    if not title and title_id.startswith(("tvmaze-", "itunes-")):
        from app.services.metadata import itunes_by_id, tvmaze_by_id
        prefix, _, raw_id = title_id.partition("-")
        if raw_id.isdigit():
            found = tvmaze_by_id(int(raw_id)) if prefix == "tvmaze" else itunes_by_id(int(raw_id))
            if found:
                return JsonResponse({**found, "title_id": title_id, "kind": "series" if prefix == "tvmaze" else "movie"})
    if not title and title_id.startswith("anilist-") and title_id.removeprefix("anilist-").isdigit():
        from app.services.metadata import anilist_by_id
        found = anilist_by_id(int(title_id.removeprefix("anilist-")))
        if found:
            return JsonResponse({**found, "title_id": title_id, "kind": "anime"})
    if not title:
        return _error("Title not found in the current reference index.", 404)
    if not settings.METADATA_ENRICHMENT_ENABLED:
        return JsonResponse(title)
    cache = MetadataCache.objects.filter(pk=title_id).first()
    now = timezone.now()
    if cache and now - cache.fetched_at < timedelta(hours=max(1, settings.METADATA_CACHE_HOURS)):
        return JsonResponse(cache.data)
    enriched = enrich_metadata(title)
    try:
        MetadataCache.objects.update_or_create(title_id=title_id, defaults={"data": enriched, "fetched_at": now})
    except Exception:
        logger.warning("Metadata cache could not be updated")
    return JsonResponse(enriched)

@require_http_methods(["GET"])
def accuracy_stats(request):
    from core.models import Feedback
    report = None
    try:
        path = Path(settings.EVALUATION_REPORT_PATH)
        if path.exists():
            report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.warning("Evaluation report could not be read")
    counts = {v: 0 for v in ("correct", "wrong", "unknown")}
    counts.update({row["verdict"]: row["n"] for row in Feedback.objects.values("verdict").annotate(n=Count("id"))
                   if row["verdict"] in counts})
    return JsonResponse({"evaluation_available": report is not None, "evaluation": report,
        "feedback_count": sum(counts.values()), "feedback_verdicts": counts,
        "disclaimer": "Accuracy is not claimed until a labeled evaluation set has been run." if report is None else "Metrics are from the labeled fixture set, not a guarantee for arbitrary uploads."})

@csrf_exempt
@require_http_methods(["POST"])
def submit_takedown(request):
    from core.models import TakedownRequest
    payload = _json_body(request)
    if not payload or not payload.get("source_url") or not payload.get("reason"):
        return _error("source_url and reason are required.")
    source_url, reason = str(payload["source_url"]).strip(), str(payload["reason"]).strip()
    parsed = urlparse(source_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc or len(source_url) > 2000:
        return _error("source_url must be an http(s) URL of at most 2000 characters.")
    if not 10 <= len(reason) <= 4000:
        return _error("reason must be between 10 and 4000 characters.")
    email = (str(payload.get("contact_email") or "")).strip() or None
    if email:
        try:
            validate_email(email)
        except ValidationError:
            return _error("contact_email is not a valid email address.")
    item = TakedownRequest.objects.create(source_url=source_url, reason=reason, contact_email=email)
    return JsonResponse({"id": item.id, "status": "received", "message": "The removal request has been recorded for review."}, status=202)

@require_http_methods(["GET"])
def search(request):
    query = request.GET.get("q", "").strip()
    if len(query) < 2 or len(query) > 120:
        return _error("q must be between 2 and 120 characters.")
    try:
        results = search_titles(query)
        return JsonResponse({"query": query, "results": results})
    except Exception:
        logger.exception("Title search failed")
        return _error("Search is temporarily unavailable.", 502)

@require_http_methods(["GET"])
def reference_status(request):
    index = load_index()
    return JsonResponse({"ready": bool(index.get("frames")), "algorithm": index.get("algorithm", "unknown"),
        "titles": len(index.get("titles", [])), "frames": len(index.get("frames", [])), "index_version": index.get("version", 1)})
