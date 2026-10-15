import logging
import threading
import time
import uuid
from collections import deque

from django.conf import settings
from django.http import HttpResponse, JsonResponse

logger = logging.getLogger("sceneseek.http")


def client_ip(request) -> str:
    if getattr(settings, "TRUST_PROXY_HEADERS", True):
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()[:64] or "unknown"
    return request.META.get("REMOTE_ADDR", "unknown")


class RequestIdMiddleware:
    """Attach an ``X-Request-ID`` to every response and log slow/failed requests."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = (request.headers.get("X-Request-ID") or "").strip()[:64] or uuid.uuid4().hex[:16]
        request.request_id = rid
        started = time.perf_counter()
        response = self.get_response(request)
        elapsed = (time.perf_counter() - started) * 1000
        response["X-Request-ID"] = rid
        if response.status_code >= 500 or elapsed > 3000:
            logger.warning("%s %s -> %s in %.0f ms [%s]", request.method, request.path,
                           response.status_code, elapsed, rid)
        return response


class CorsMiddleware:
    ALLOWED_METHODS = "GET, POST, DELETE, OPTIONS"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        origin = request.headers.get("Origin", "")
        if request.method == "OPTIONS" and request.headers.get("Access-Control-Request-Method"):
            response = HttpResponse(status=204)
        else:
            response = self.get_response(request)
        if origin and origin.rstrip("/") in settings.CORS_ORIGINS:
            response["Access-Control-Allow-Origin"] = origin
            response["Vary"] = "Origin"
            response["Access-Control-Allow-Methods"] = self.ALLOWED_METHODS
            response["Access-Control-Allow-Headers"] = "Content-Type, Authorization, X-Request-ID"
            response["Access-Control-Expose-Headers"] = "Retry-After, X-Request-ID"
            response["Access-Control-Max-Age"] = "600"
        return response


class RateLimitMiddleware:
    """Small in-memory sliding-window limiter (per process, per client IP).

    Uploads (``POST /v1/identify``) use ``API_RATE_LIMIT_PER_MINUTE``; other ``/v1`` calls use
    ``READ_RATE_LIMIT_PER_MINUTE``. For multi-instance deployments also rate-limit at the edge.
    """

    WINDOW = 60.0
    MAX_KEYS = 20000

    def __init__(self, get_response):
        self.get_response = get_response
        self._hits: dict[str, deque] = {}
        self._lock = threading.Lock()
        self._last_sweep = time.monotonic()

    def _limit_for(self, request):
        path = request.path
        if not path.startswith("/v1/") or request.method == "OPTIONS":
            return None
        if request.method == "POST" and path.rstrip("/") == "/v1/identify":
            return "identify", settings.API_RATE_LIMIT_PER_MINUTE
        if request.method in {"POST", "DELETE"}:
            return "write", max(settings.API_RATE_LIMIT_PER_MINUTE * 3, 30)
        return "read", settings.READ_RATE_LIMIT_PER_MINUTE

    def _sweep(self, now):
        if now - self._last_sweep < 120 and len(self._hits) < self.MAX_KEYS:
            return
        self._last_sweep = now
        for key in [k for k, q in self._hits.items() if not q or now - q[-1] > self.WINDOW]:
            self._hits.pop(key, None)

    def __call__(self, request):
        rule = self._limit_for(request) if settings.RATE_LIMIT_ENABLED else None
        if rule:
            bucket, limit = rule
            key = f"{bucket}:{client_ip(request)}"
            now = time.monotonic()
            with self._lock:
                self._sweep(now)
                hits = self._hits.setdefault(key, deque())
                while hits and now - hits[0] > self.WINDOW:
                    hits.popleft()
                if len(hits) >= limit:
                    retry = max(1, int(self.WINDOW - (now - hits[0])) + 1)
                    response = JsonResponse({"detail": f"Too many requests. Please wait {retry} seconds and try again."}, status=429)
                    response["Retry-After"] = str(retry)
                    return response
                hits.append(now)
        return self.get_response(request)
