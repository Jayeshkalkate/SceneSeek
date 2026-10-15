"""Free online anime scene lookup (trace.moe) with AniList metadata.

trace.moe needs no API key (fair-use rate limits apply). The frame is sent to
that third-party service, so this is switchable with ENABLE_ONLINE_ANIME.
It only recognises anime; movies/series still need a local reference index.
"""
from __future__ import annotations
import logging
import re
from pathlib import Path
from typing import Any
import httpx

logger = logging.getLogger(__name__)
TRACE_URL = "https://api.trace.moe/search"
ANILIST_URL = "https://graphql.anilist.co"
UA = {"User-Agent": "SceneSeek/1.0 (student project)"}
TIMEOUT = httpx.Timeout(25.0, connect=6.0)
MAX_QUERY_FRAMES = 3


def _band(similarity: float) -> str:
    # trace.moe documents results below ~0.90 as frequently wrong.
    if similarity >= 0.92:
        return "high"
    if similarity >= 0.86:
        return "medium"
    return "low"


def pick_frames(paths: list[Path], limit: int = MAX_QUERY_FRAMES) -> list[Path]:
    if len(paths) <= limit:
        return list(paths)
    step = (len(paths) - 1) / (limit - 1)
    return [paths[round(i * step)] for i in range(limit)]


def parse_trace_response(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Normalise trace.moe results (adult titles are dropped)."""
    out: list[dict[str, Any]] = []
    for row in payload.get("result") or []:
        info = row.get("anilist")
        if not isinstance(info, dict):
            continue
        if info.get("isAdult"):
            continue
        names = info.get("title") or {}
        title = names.get("english") or names.get("romaji") or names.get("native")
        if not title or info.get("id") is None:
            continue
        try:
            similarity = max(0.0, min(1.0, float(row.get("similarity") or 0)))
        except (TypeError, ValueError):
            continue
        out.append({
            "anilist_id": int(info["id"]), "title": str(title), "original_title": names.get("native"),
            "similarity": similarity, "episode": row.get("episode"),
            "timestamp_s": row.get("from"), "preview_url": row.get("image"),
        })
    return out


def _search_one(client: httpx.Client, frame: Path) -> list[dict[str, Any]]:
    resp = client.post(TRACE_URL, params={"anilistInfo": "", "cutBorders": ""},
                       files={"image": (frame.name, frame.read_bytes(), "image/jpeg")})
    if resp.status_code == 429:
        logger.warning("trace.moe rate limit reached")
        return []
    resp.raise_for_status()
    return parse_trace_response(resp.json())


def _anilist_meta(client: httpx.Client, anilist_id: int) -> dict[str, Any]:
    query = ("query ($id: Int) { Media(id: $id, type: ANIME) { description(asHtml: false) startDate { year } "
             "genres siteUrl coverImage { large } averageScore format } }")
    try:
        r = client.post(ANILIST_URL, json={"query": query, "variables": {"id": anilist_id}})
        r.raise_for_status()
        media = (r.json().get("data") or {}).get("Media") or {}
    except (httpx.HTTPError, ValueError):
        return {}
    return {
        "year": (media.get("startDate") or {}).get("year"),
        "synopsis": re.sub(r"<[^>]+>", "", media.get("description") or "")[:1500],
        "genres": media.get("genres") or [], "poster_url": (media.get("coverImage") or {}).get("large"),
        "rating": {"value": media.get("averageScore"), "source": "AniList (/100)"},
        "external_url": media.get("siteUrl"),
    }


def lookup_anime(frames: list[Path], max_candidates: int = 5) -> list[dict[str, Any]]:
    """Return candidate dicts (same shape as fuse output) or [] when nothing/unavailable."""
    best: dict[int, dict[str, Any]] = {}
    with httpx.Client(timeout=TIMEOUT, headers=UA) as client:
        for frame in pick_frames(frames):
            try:
                rows = _search_one(client, frame)
            except (httpx.HTTPError, ValueError, OSError):
                logger.info("trace.moe lookup failed for a frame", exc_info=True)
                continue
            for row in rows:
                cur = best.get(row["anilist_id"])
                if cur is None or row["similarity"] > cur["similarity"]:
                    best[row["anilist_id"]] = row
        ranked = sorted(best.values(), key=lambda r: -r["similarity"])[:max_candidates]
        candidates = []
        for i, row in enumerate(ranked):
            meta = _anilist_meta(client, row["anilist_id"]) if i < 3 else {}
            candidates.append({
                "title_id": f"anilist-{row['anilist_id']}", "title": row["title"],
                "original_title": row["original_title"], "kind": "anime", "year": meta.get("year"),
                "synopsis": meta.get("synopsis"), "genres": meta.get("genres") or [],
                "poster_url": meta.get("poster_url") or row.get("preview_url"),
                "rating": meta.get("rating") or {"value": None, "source": None},
                "external_url": meta.get("external_url") or f"https://anilist.co/anime/{row['anilist_id']}",
                "provider": "trace.moe + AniList", "attribution": "Scene match by trace.moe; metadata by AniList.",
                "score": round(row["similarity"], 4), "confidence": _band(row["similarity"]),
                "evidence": {"visual": round(row["similarity"], 4)},
                "episode": row.get("episode") if isinstance(row.get("episode"), (int, str)) else None,
                "timestamp_s": round(float(row["timestamp_s"]), 1) if isinstance(row.get("timestamp_s"), (int, float)) else None,
                "preview_url": row.get("preview_url"),
            })
    return candidates
