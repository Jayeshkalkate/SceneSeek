from pathlib import Path, PurePosixPath
from urllib.parse import quote
import httpx
from app.config import get_settings


class StorageError(RuntimeError):
    pass


def _supabase_enabled() -> bool:
    s = get_settings()
    return bool(s.supabase_url.strip() and s.supabase_service_key.strip())


def _headers() -> dict[str, str]:
    s = get_settings()
    return {
        "Authorization": f"Bearer {s.supabase_service_key}",
        "apikey": s.supabase_service_key,
    }


def store_upload(data: bytes, key: str, content_type: str) -> str:
    """Store private upload; returns an opaque local: or supabase: URI for the worker."""
    s = get_settings()
    safe_parts = PurePosixPath(key).parts
    if not safe_parts or any(p in {"", ".", ".."} for p in safe_parts) or key.startswith("/"):
        raise ValueError("Invalid generated storage key")
    if _supabase_enabled():
        url = f"{s.supabase_url.rstrip('/')}/storage/v1/object/{quote(s.supabase_bucket, safe='')}/{quote(key, safe='/')}"
        headers = {**_headers(), "Content-Type": content_type, "x-upsert": "false"}
        try:
            response = httpx.post(url, headers=headers, content=data, timeout=30)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise StorageError("Could not store upload in configured private storage") from exc
        return f"supabase://{s.supabase_bucket}/{key}"

    base = Path(s.upload_dir).resolve()
    destination = (base / Path(*safe_parts)).resolve()
    if base not in destination.parents:
        raise ValueError("Invalid storage destination")
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive create prevents accidental overwrite in the unlikely event of a collision.
    with destination.open("xb") as stream:
        stream.write(data)
    return f"local://{destination}"


def read_upload(uri: str) -> bytes:
    s = get_settings()
    if uri.startswith("local://"):
        path = Path(uri.removeprefix("local://")).resolve()
        base = Path(s.upload_dir).resolve()
        if base not in path.parents:
            raise ValueError("Upload path is outside the configured upload directory")
        return path.read_bytes()
    if uri.startswith("supabase://"):
        bucket_and_key = uri.removeprefix("supabase://")
        bucket, _, key = bucket_and_key.partition("/")
        if not bucket or not key or ".." in PurePosixPath(key).parts:
            raise ValueError("Invalid remote upload path")
        url = f"{s.supabase_url.rstrip('/')}/storage/v1/object/{quote(bucket, safe='')}/{quote(key, safe='/')}"
        try:
            response = httpx.get(url, headers=_headers(), timeout=60)
            response.raise_for_status()
            return response.content
        except httpx.HTTPError as exc:
            raise StorageError("Could not retrieve upload from configured private storage") from exc
    raise ValueError("Unknown upload storage URI")


def delete_upload(uri: str | None) -> None:
    if not uri:
        return
    s = get_settings()
    if uri.startswith("local://"):
        path = Path(uri.removeprefix("local://")).resolve()
        base = Path(s.upload_dir).resolve()
        if base in path.parents:
            path.unlink(missing_ok=True)
        return
    if uri.startswith("supabase://") and _supabase_enabled():
        bucket_and_key = uri.removeprefix("supabase://")
        bucket, _, key = bucket_and_key.partition("/")
        if not bucket or not key or ".." in PurePosixPath(key).parts:
            return
        url = f"{s.supabase_url.rstrip('/')}/storage/v1/object/{quote(bucket, safe='')}"
        try:
            response = httpx.delete(url, headers={**_headers(), "Content-Type": "application/json"}, json={"prefixes": [key]}, timeout=20)
            response.raise_for_status()
        except httpx.HTTPError:
            # TTL/lifecycle cleanup remains the fallback if the provider is unavailable.
            pass


def cleanup_local_uploads(older_than_seconds: int) -> int:
    s = get_settings()
    import time
    cutoff = time.time() - older_than_seconds
    removed = 0
    root = Path(s.upload_dir).resolve()
    for path in root.rglob("*"):
        if path.is_file() and path.name != ".gitkeep":
            try:
                if path.stat().st_mtime < cutoff:
                    path.unlink(missing_ok=True)
                    removed += 1
            except OSError:
                continue
    return removed
