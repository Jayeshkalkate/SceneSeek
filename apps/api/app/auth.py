"""Compatibility token helpers used by tests and offline tools; HTTP auth lives in Django views."""
import base64
import hashlib
import hmac
import json
import time
from app.config import get_settings

def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def _sign(body: str) -> str:
    return _b64(hmac.new(get_settings().jwt_secret.encode(), body.encode(), hashlib.sha256).digest())

def create_token(user_id: str) -> str:
    settings = get_settings()
    if not settings.jwt_secret:
        raise RuntimeError("JWT_SECRET missing")
    body = _b64(json.dumps({"sub": user_id, "exp": int(time.time() + settings.jwt_ttl_hours * 3600)}, separators=(",", ":")).encode())
    return f"{body}.{_sign(body)}"

def decode_token(token: str) -> str | None:
    if not get_settings().jwt_secret:
        return None
    try:
        body, sig = token.split(".", 1)
        if not hmac.compare_digest(sig, _sign(body)):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        return str(payload["sub"]) if int(payload["exp"]) > time.time() else None
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        return None
