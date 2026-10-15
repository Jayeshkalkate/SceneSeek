from __future__ import annotations
from collections import defaultdict
from typing import Any

W_VISUAL, W_TEXT, W_AUDIO = 0.78, 0.17, 0.05


def fuse_scores(
    per_title_frame_scores: dict[str, list[float]],
    query_frame_count: int,
    title_map: dict[str, dict[str, Any]],
    text_scores: dict[str, float] | None = None,
    audio_scores: dict[str, float] | None = None,
    visual_method: str = "dhash",
    max_candidates: int = 5,
) -> dict[str, Any]:
    """Deterministic ranking; score is a retrieval score, not a calibrated probability."""
    text_scores = text_scores or {}
    audio_scores = audio_scores or {}
    scored = []
    for title_id, similarities in per_title_frame_scores.items():
        if not similarities or title_id not in title_map:
            continue
        usable = sorted((max(0.0, min(1.0, float(x))) for x in similarities), reverse=True)
        best = usable[0]
        top3 = sum(usable[:3]) / min(3, len(usable))
        coverage = min(1.0, sum(s >= 0.55 for s in usable) / max(1, query_frame_count))
        visual = 0.50 * best + 0.30 * top3 + 0.20 * coverage
        has_text = title_id in text_scores
        has_audio = title_id in audio_scores
        denominator = W_VISUAL + (W_TEXT if text_scores else 0) + (W_AUDIO if audio_scores else 0)
        score = W_VISUAL * visual
        if text_scores:
            score += W_TEXT * text_scores.get(title_id, 0.0)
        if audio_scores:
            score += W_AUDIO * audio_scores.get(title_id, 0.0)
        score /= denominator
        scored.append({
            "title_id": str(title_id),
            "score": round(max(0.0, min(1.0, score)), 4),
            "evidence": {
                "visual": round(visual, 4),
                "text": round(text_scores.get(title_id, 0.0), 4),
                "audio": round(audio_scores.get(title_id, 0.0), 4),
            },
        })
    scored.sort(key=lambda row: (-row["score"], row["title_id"]))
    if not scored:
        return {"band": "none", "margin": 0.0, "candidates": [], "visual_method": visual_method,
                "message": "No reference index is available yet. Add reference frames, then rebuild the index."}

    margin = scored[0]["score"] - (scored[1]["score"] if len(scored) > 1 else 0.0)
    best_score = scored[0]["score"]
    if best_score < 0.35:
        return {"band": "none", "margin": round(margin, 4), "candidates": [], "visual_method": visual_method,
                "message": "No useful visual match was found. Try a clearer frame or expand the reference collection."}
    if best_score >= 0.82 and margin >= 0.06:
        band = "high"
    elif best_score >= 0.62 and margin >= 0.02:
        band = "medium"
    else:
        band = "low"

    candidates = []
    for index, row in enumerate(scored[:max_candidates]):
        source = title_map[row["title_id"]]
        rating = source.get("rating") or {"value": None, "source": None}
        if not isinstance(rating, dict):
            rating = {"value": rating, "source": source.get("rating_source")}
        candidates.append({
            "title_id": row["title_id"],
            "title": str(source.get("title") or "Untitled"),
            "original_title": source.get("original_title"),
            "kind": source.get("kind", "unknown"),
            "year": source.get("year"),
            "synopsis": source.get("synopsis"),
            "genres": source.get("genres") or [],
            "poster_url": source.get("poster_url"),
            "rating": rating,
            "external_url": source.get("external_url"),
            "provider": source.get("provider", "manual"),
            "attribution": source.get("attribution"),
            "score": row["score"],
            "confidence": band if index == 0 else "low",
            "evidence": row["evidence"],
        })
    return {"band": band, "margin": round(margin, 4), "candidates": candidates,
            "visual_method": visual_method, "message": None}
