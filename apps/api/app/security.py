import time
from collections import defaultdict, deque
from threading import Lock
from uuid import uuid4
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from app.config import get_settings


class UploadBodyLimitMiddleware:
    """Cap both declared and streamed bodies before multipart parsing consumes the upload."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope.get("type") != "http" or scope.get("path") != "/v1/identify" or scope.get("method") != "POST":
            await self.app(scope, receive, send)
            return
        maximum = get_settings().max_video_bytes + 1024 * 1024  # headroom for multipart headers
        headers = {key.lower(): value for key, value in scope.get("headers", [])}
        declared = headers.get(b"content-length")
        if declared:
            try:
                if int(declared) > maximum:
                    response = JSONResponse(status_code=413, content={"detail": "Request body exceeds the upload limit."})
                    await response(scope, receive, send)
                    return
            except ValueError:
                response = JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header."})
                await response(scope, receive, send)
                return
        received = 0

        async def limited_receive():
            nonlocal received
            message = await receive()
            if message.get("type") == "http.request":
                received += len(message.get("body", b""))
                if received > maximum:
                    raise _UploadTooLarge()
            return message

        try:
            await self.app(scope, limited_receive, send)
        except _UploadTooLarge:
            response = JSONResponse(status_code=413, content={"detail": "Request body exceeds the upload limit."})
            await response(scope, receive, send)


class _UploadTooLarge(Exception):
    pass


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Small single-process sliding-window limiter; use a shared edge limiter at scale."""
    def __init__(self, app):
        super().__init__(app)
        self._events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._last_cleanup = 0.0

    async def dispatch(self, request: Request, call_next):
        if request.url.path in {"/ping", "/healthz"}:
            return await call_next(request)
        settings = get_settings()
        client_ip = request.client.host if request.client else "unknown"
        group = "upload" if request.url.path == "/v1/identify" else "read"
        limit = settings.api_rate_limit_per_minute if group == "upload" else settings.read_rate_limit_per_minute
        key = (client_ip, group)
        now = time.monotonic()
        with self._lock:
            if now - self._last_cleanup > 60:
                stale = [entry_key for entry_key, values in self._events.items() if not values or now - values[-1] >= 60]
                for entry_key in stale:
                    self._events.pop(entry_key, None)
                self._last_cleanup = now
            events = self._events[key]
            while events and now - events[0] >= 60:
                events.popleft()
            if len(events) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit reached. Please wait a moment and try again."},
                    headers={"Retry-After": "60", "X-Content-Type-Options": "nosniff"},
                )
            events.append(now)
        request_id = request.headers.get("x-request-id", str(uuid4()))[:80]
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response
