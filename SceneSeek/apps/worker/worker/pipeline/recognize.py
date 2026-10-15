from __future__ import annotations
import logging
from pathlib import Path
from sqlalchemy import text as sql_text
from app.database import engine
from typing import Any
from app.config import get_settings
from app.services.fuse import fuse_scores
from app.services.media import dhash, prepare_image
from app.services.reference_index import load_index
from worker.models.clip import embed_images
from worker.pipeline.text_signals import calculate_text_scores, extract_ocr, transcribe_video

logger = logging.getLogger(__name__)


def _title_id(item: dict[str, Any]) -> str:
    return str(item.get("title_id", item.get("id", "")))


def _recognize_local(frame_paths: list[Path], work_dir: Path, video_path: Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    index = load_index()
    titles = index.get("titles") or []
    references = index.get("frames") or []
    algorithm = str(index.get("algorithm") or "dhash").lower()
    if not references or not titles:
        return {"band": "none", "margin": 0.0, "candidates": [], "signals_used": [],
                "latency_ms": 0, "visual_method": algorithm,
                "message": "SceneSeek has no reference frames yet. Add lawful reference material and rebuild the index."}
    if algorithm not in {"dhash", "clip"}:
        raise RuntimeError(f"Unsupported reference index algorithm: {algorithm}")

    per_title: dict[str, list[float]] = {_title_id(title): [] for title in titles if _title_id(title)}
    query_vectors = None
    reference_matrix = None
    reference_title_ids: list[str] = []
    if algorithm == "clip":
        import numpy as np
        query_vectors = embed_images(frame_paths, settings.clip_model)
        if settings.use_pgvector:
            if not engine.dialect.name.startswith("postgresql"):
                raise RuntimeError("USE_PGVECTOR=true requires a PostgreSQL DATABASE_URL and the SceneSeek Supabase migration.")
            for query_vector in query_vectors:
                vector_literal = "[" + ",".join(f"{float(value):.7f}" for value in query_vector) + "]"
                with engine.connect() as connection:
                    rows = connection.execute(sql_text("""
                        SELECT rf.title_id, 1 - (rf.embedding <=> CAST(:embedding AS vector)) AS similarity
                        FROM ref_frames rf
                        ORDER BY rf.embedding <=> CAST(:embedding AS vector)
                        LIMIT 60
                    """), {"embedding": vector_literal}).mappings().all()
                best_by_title: dict[str, float] = {}
                for row in rows:
                    tid = str(row["title_id"])
                    if tid not in per_title:
                        continue
                    score = max(0.0, min(1.0, (float(row["similarity"]) - 0.10) / 0.55))
                    best_by_title[tid] = max(best_by_title.get(tid, 0.0), score)
                for tid in per_title:
                    per_title[tid].append(best_by_title.get(tid, 0.0))
        else:
            reference_vectors = []
            for item in references:
                vector = item.get("embedding")
                if not isinstance(vector, list) or len(vector) != 512:
                    raise RuntimeError("The CLIP reference index contains missing or invalid embeddings; rebuild it.")
                reference_vectors.append(vector)
                reference_title_ids.append(str(item.get("title_id", "")))
            if not reference_vectors:
                return {"band": "none", "margin": 0.0, "candidates": [], "signals_used": [],
                        "latency_ms": 0, "visual_method": algorithm, "message": "No reference embeddings are available."}
            reference_matrix = np.asarray(reference_vectors, dtype=np.float32)
            norms = np.linalg.norm(reference_matrix, axis=1, keepdims=True)
            reference_matrix = reference_matrix / np.maximum(norms, 1e-12)
            # Convert cosine similarity to a retrieval scale. This is an engineering heuristic, not a probability.
            similarities = query_vectors @ reference_matrix.T
            for q_index in range(len(frame_paths)):
                best_by_title: dict[str, float] = {}
                for ref_index, raw_similarity in enumerate(similarities[q_index]):
                    tid = reference_title_ids[ref_index]
                    if tid not in per_title:
                        continue
                    score = max(0.0, min(1.0, (float(raw_similarity) - 0.10) / 0.55))
                    if score > best_by_title.get(tid, 0.0):
                        best_by_title[tid] = score
                for tid in per_title:
                    per_title[tid].append(best_by_title.get(tid, 0.0))
    else:
        reference_hashes: list[tuple[str, int]] = []
        for item in references:
            raw = item.get("dhash", item.get("phash"))
            if raw is None:
                continue
            try:
                value = int(str(raw), 16) if isinstance(raw, str) else int(raw)
                reference_hashes.append((str(item.get("title_id", "")), value))
            except (TypeError, ValueError):
                continue
        for frame_path in frame_paths:
            with prepare_image(frame_path) as image:
                query_hash = dhash(image)
            best_by_title: dict[str, float] = {}
            for tid, reference_hash in reference_hashes:
                if tid not in per_title:
                    continue
                distance = (query_hash ^ reference_hash).bit_count()
                # Random images sit near 0.5 similarity; rescale so only close hashes score.
                score = max(0.0, min(1.0, ((1.0 - distance / 64.0) - 0.70) / 0.25))
                if score > best_by_title.get(tid, 0.0):
                    best_by_title[tid] = score
            for tid in per_title:
                per_title[tid].append(best_by_title.get(tid, 0.0))

    signals_used = ["visual"]
    ocr_text = extract_ocr(frame_paths)
    transcript = transcribe_video(video_path, work_dir) if video_path else ""
    text_scores = calculate_text_scores(ocr_text, titles) if ocr_text.strip() else {}
    audio_scores = calculate_text_scores(transcript, titles) if transcript.strip() else {}
    if ocr_text.strip():
        signals_used.append("ocr")
    if transcript.strip():
        signals_used.append("asr")

    result = fuse_scores(per_title, len(frame_paths), {_title_id(title): title for title in titles},
                         text_scores=text_scores, audio_scores=audio_scores, visual_method=algorithm)
    result["signals_used"] = signals_used
    extracted_text = " ".join(x for x in (ocr_text.strip(), transcript.strip()) if x)
    result["scene_caption"] = extracted_text[:300] or None
    return result


def _norm(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def merge_results(local: dict[str, Any], online: list[dict[str, Any]]) -> dict[str, Any]:
    """Combine local-index candidates with online anime candidates (best score first)."""
    if not online:
        return local
    pool = [dict(c, _src="local") for c in (local.get("candidates") or [])] + [dict(c, _src="online") for c in online]
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for cand in sorted(pool, key=lambda c: -float(c.get("score", 0))):
        key = _norm(str(cand.get("title", "")))
        if key in seen:
            continue
        seen.add(key)
        merged.append(cand)
    merged = merged[:5]
    top = merged[0]
    band = top["confidence"] if top["_src"] == "online" else local.get("band", "low")
    for i, cand in enumerate(merged):
        if i > 0:
            cand["confidence"] = "low"
        cand.pop("_src", None)
    margin = float(top["score"]) - (float(merged[1]["score"]) if len(merged) > 1 else 0.0)
    result = dict(local)
    result.update({"band": band, "margin": round(margin, 4), "candidates": merged, "message": None})
    result["signals_used"] = sorted(set(local.get("signals_used") or []) | {"online-anime"})
    if not local.get("candidates"):
        result["visual_method"] = "trace.moe"
    return result


def recognize(frame_paths: list[Path], work_dir: Path, video_path: Path | None = None,
              use_online: bool | None = None) -> dict[str, Any]:
    settings = get_settings()
    local = _recognize_local(frame_paths, work_dir, video_path=video_path)
    if use_online is None:
        use_online = settings.enable_online_anime
    if not use_online:
        return local
    try:
        from worker.pipeline.online import lookup_anime
        online = lookup_anime(frame_paths)
    except Exception:  # never fail a job because a free third-party service is down
        logger.warning("Online anime lookup failed", exc_info=True)
        online = []
    result = merge_results(local, online)
    if not result.get("candidates") and not local.get("candidates"):
        result["message"] = ("No match found. Online lookup covers anime only; movies and series need titles added "
                             "to the reference index (see README).")
    return result
