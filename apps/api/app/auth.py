"""Google Sign-In (ID token) + small HMAC session tokens. Free, no extra dependencies."""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4
import httpx
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.config import get_settings
from app.database import get_db
from app.models import User, utcnow

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _sign(body: str) -> str:
    return _b64(hmac.new(get_settings().jwt_secret.encode(), body.encode(), hashlib.sha256).digest())


def create_token(user_id: str) -> str:
    s = get_settings()
    if not s.jwt_secret:
        raise HTTPException(status_code=503, detail="Sign-in is not configured (JWT_SECRET missing).")
    body = _b64(json.dumps({"sub": user_id, "exp": int(time.time() + s.jwt_ttl_hours * 3600)}, separators=(",", ":")).encode())
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


def verify_google_credential(credential: str) -> dict:
    """Validate a Google ID token with Google's tokeninfo endpoint (signature + expiry), then check audience."""
    s = get_settings()
    if not s.google_client_id or not s.jwt_secret:
        raise HTTPException(status_code=503, detail="Google sign-in is not configured on this server.")
    try:
        r = httpx.get("https://oauth2.googleapis.com/tokeninfo", params={"id_token": credential}, timeout=10)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not reach Google to verify sign-in.") from exc
    if r.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid Google sign-in token.")
    data = r.json()
    if data.get("aud") != s.google_client_id or data.get("iss") not in GOOGLE_ISSUERS:
        raise HTTPException(status_code=401, detail="Google token was issued for a different app.")
    if str(data.get("email_verified")).lower() != "true" or not data.get("sub") or not data.get("email"):
        raise HTTPException(status_code=401, detail="Google account email is not verified.")
    return data


def upsert_user(db: Session, info: dict) -> User:
    user = db.scalar(select(User).where(User.google_sub == info["sub"]))
    if user is None:
        user = User(id=str(uuid4()), google_sub=info["sub"], email=info["email"], name=info.get("name"), picture=info.get("picture"))
        db.add(user)
    else:
        user.email, user.name, user.picture, user.last_login = info["email"], info.get("name"), info.get("picture"), utcnow()
    db.commit()
    db.refresh(user)
    return user


def optional_user(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> User | None:
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    user_id = decode_token(authorization[7:].strip())
    return db.get(User, user_id) if user_id else None


def required_user(user: User | None = Depends(optional_user)) -> User:
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in with Google.")
    return user
