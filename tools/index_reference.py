#!/usr/bin/env python3
"""Build an idempotent JSON reference index from lawfully sourced reference frames."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))
sys.path.insert(0, str(ROOT / "apps" / "worker"))
from app.config import get_settings  # noqa: E402
from app.services.media import dhash, hamming_distance, prepare_image  # noqa: E402


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "untitled"


def _load_metadata(metadata_path: Path, title_id: str) -> dict[str, Any]:
    if not metadata_path.exists():
        raise ValueError(f"Missing metadata file: {metadata_path}")
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not str(data.get("title", "")).strip():
        raise ValueError(f"{metadata_path} must contain a non-empty 'title'")
    if data.get("title_id") is not None and not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", str(data["title_id"])):
        raise ValueError(f"title_id must use only letters, digits, underscore, or hyphen in {metadata_path}")
    kind = str(data.get("kind", "unknown")).lower()
    if kind not in {"anime", "movie", "series", "unknown"}:
        raise ValueError(f"Invalid kind '{kind}' in {metadata_path}; use anime/movie/series/unknown")
    genres = data.get("genres") or []
    if not isinstance(genres, list) or not all(isinstance(item, str) for item in genres):
        raise ValueError(f"'genres' must be a list of strings in {metadata_path}")
    rating = data.get("rating") or {"value": None, "source": None}
    if not isinstance(rating, dict):
        rating = {"value": rating, "source": data.get("rating_source")}
    return {
        "title_id": str(data.get("title_id") or title_id),
        "title": str(data["title"]).strip(),
        "original_title": data.get("original_title"),
        "kind": kind,
        "year": data.get("year") if isinstance(data.get("year"), int) else None,
        "synopsis": str(data.get("synopsis") or "")[:4000],
        "genres": genres[:30],
        "poster_url": data.get("poster_url"),
        "rating": rating,
        "external_url": data.get("external_url"),
        "provider": data.get("provider", "manual"),
        "attribution": str(data.get("attribution") or "")[:1500],
    }


def build(reference_dir: Path, output: Path, algorithm: str, model_name: str) -> dict[str, Any]:
    reference_dir = reference_dir.resolve()
    titles: list[dict[str, Any]] = []
    frames: list[dict[str, Any]] = []
    if not reference_dir.exists():
        raise FileNotFoundError(f"Reference directory does not exist: {reference_dir}")

    for title_dir in sorted(path for path in reference_dir.iterdir() if path.is_dir()):
        frame_dir = title_dir / "frames"
        if not frame_dir.is_dir():
            continue
        candidates = sorted(path for path in frame_dir.iterdir() if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
        if not candidates:
            continue
        metadata = _load_metadata(title_dir / "metadata.json", _slug(title_dir.name))
        title_id = metadata["title_id"]
        before = len(frames)
        hash_values: list[int] = []
        hashes: list[str] = []
        valid_paths: list[Path] = []
        # Indexing may use hundreds of frames per title; query-time sampling is capped separately.
        # Keep the reference set comprehensive while skipping near-identical images.
        for frame_path in candidates:
            try:
                with prepare_image(frame_path, max_width=1024) as image:
                    hash_int = dhash(image)
                if any(hamming_distance(hash_int, previous) <= 6 for previous in hash_values):
                    continue
                hash_values.append(hash_int)
                hashes.append(f"{hash_int:016x}")
                valid_paths.append(frame_path)
            except Exception as exc:
                print(f"WARN: skipping unreadable frame {frame_path}: {exc}", file=sys.stderr)
        embeddings = None
        if algorithm == "clip" and valid_paths:
            from worker.models.clip import embed_images  # optional dependency, loaded only for CLIP mode
            embeddings = embed_images(valid_paths, model_name).tolist()
        for i, frame_path in enumerate(valid_paths):
            entry: dict[str, Any] = {
                "title_id": title_id,
                "path": str(frame_path.resolve().relative_to(reference_dir)),
                "dhash": hashes[i],
            }
            if embeddings is not None:
                entry["embedding"] = [round(float(x), 6) for x in embeddings[i]]
            frames.append(entry)
        if len(frames) > before:
            titles.append(metadata)
            print(f"Indexed {len(frames) - before:4d} frame(s): {metadata['title']} [{title_id}]")

    if not frames:
        raise ValueError("No valid reference frames were found. Add <title>/metadata.json and <title>/frames/* first.")
    index = {"version": 1, "algorithm": algorithm, "embedding_model": model_name if algorithm == "clip" else None,
             "reference_root": str(reference_dir), "titles": titles, "frames": frames}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output.with_suffix(output.suffix + ".tmp")
    temp_path.write_text(json.dumps(index, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    temp_path.replace(output)
    print(f"Wrote {len(frames)} frame(s) across {len(titles)} title(s) to {output}")
    if algorithm == "dhash":
        print("NOTE: dHash mostly matches duplicates/near-duplicates. Use --algorithm clip for stronger semantic visual retrieval.")
    return index


def sync_pgvector(index: dict[str, Any]) -> None:
    """Synchronize CLIP index rows into the Postgres pgvector tables created by the migration."""
    if index.get("algorithm") != "clip":
        raise ValueError("--pgvector currently requires a --algorithm clip index.")
    from sqlalchemy import text
    from app.database import engine
    if not engine.dialect.name.startswith("postgresql"):
        raise ValueError("--pgvector requires DATABASE_URL pointing to PostgreSQL.")
    with engine.begin() as conn:
        for title in index["titles"]:
            rating = title.get("rating") or {}
            conn.execute(text("""
                INSERT INTO titles (id, title, original_title, kind, year, synopsis, poster_url,
                                    genres, rating_value, rating_source, external_url, provider, attribution, raw)
                VALUES (:id, :title, :original_title, :kind, :year, :synopsis, :poster_url,
                        CAST(:genres AS jsonb), :rating_value, :rating_source, :external_url,
                        :provider, :attribution, CAST(:raw AS jsonb))
                ON CONFLICT (id) DO UPDATE SET title=EXCLUDED.title,
                  original_title=EXCLUDED.original_title, kind=EXCLUDED.kind, year=EXCLUDED.year,
                  synopsis=EXCLUDED.synopsis, poster_url=EXCLUDED.poster_url, genres=EXCLUDED.genres,
                  rating_value=EXCLUDED.rating_value, rating_source=EXCLUDED.rating_source,
                  external_url=EXCLUDED.external_url, provider=EXCLUDED.provider,
                  attribution=EXCLUDED.attribution, raw=EXCLUDED.raw, fetched_at=now()
            """), {
                "id": title["title_id"], "title": title["title"], "original_title": title.get("original_title"),
                "kind": title.get("kind", "unknown"), "year": title.get("year"), "synopsis": title.get("synopsis"),
                "poster_url": title.get("poster_url"), "genres": json.dumps(title.get("genres") or []),
                "rating_value": None if rating.get("value") is None else str(rating.get("value")),
                "rating_source": rating.get("source"), "external_url": title.get("external_url"),
                "provider": title.get("provider"), "attribution": title.get("attribution"),
                "raw": json.dumps(title, ensure_ascii=False),
            })
        title_ids = [title["title_id"] for title in index["titles"]]
        conn.execute(text("DELETE FROM ref_frames WHERE title_id = ANY(:ids)"), {"ids": title_ids})
        for frame in index["frames"]:
            conn.execute(text("""
                INSERT INTO ref_frames (title_id, frame_path, embedding, dhash)
                VALUES (:title_id, :frame_path, CAST(:embedding AS vector), CAST(:dhash AS bit(64)))
            """), {
                "title_id": frame["title_id"], "frame_path": frame.get("path", ""),
                "embedding": "[" + ",".join(f"{float(x):.7f}" for x in frame["embedding"]) + "]",
                "dhash": f"{int(frame['dhash'], 16):064b}",
            })
    print(f"Synchronized {len(index['frames'])} CLIP frame embedding(s) to PostgreSQL/pgvector.")


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, default=Path("data/reference"))
    parser.add_argument("--output", type=Path, default=Path(settings.reference_index_path))
    parser.add_argument("--algorithm", choices=["dhash", "clip"], default="dhash")
    parser.add_argument("--model", default=settings.clip_model)
    parser.add_argument("--pgvector", action="store_true", help="Also populate the Postgres pgvector tables (requires migration and DATABASE_URL).")
    args = parser.parse_args()
    if args.pgvector and args.algorithm != "clip":
        parser.error("--pgvector requires --algorithm clip because embeddings are required")
    try:
        index = build(args.reference_dir, args.output, args.algorithm, args.model)
        if args.pgvector:
            sync_pgvector(index)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
