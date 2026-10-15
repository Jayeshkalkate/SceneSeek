from __future__ import annotations
import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import Any
from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=2)
def _read_index_cached(resolved_path: str, modified_ns: int) -> dict[str, Any]:
    path = Path(resolved_path)
    with path.open("r", encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict) or not isinstance(data.get("titles", []), list) or not isinstance(data.get("frames", []), list):
        raise ValueError("Reference index has an invalid structure")
    return data


def load_index(required: bool = False) -> dict[str, Any]:
    path = Path(get_settings().reference_index_path).resolve()
    if not path.exists():
        if required:
            raise FileNotFoundError("Reference index is not ready. Add lawful reference frames and run tools/index_reference.py.")
        return {"version": 1, "algorithm": "dhash", "titles": [], "frames": []}
    try:
        return _read_index_cached(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError, json.JSONDecodeError):
        logger.exception("Unable to load the SceneSeek reference index")
        if required:
            raise
        return {"version": 1, "algorithm": "dhash", "titles": [], "frames": []}


def title_map() -> dict[str, dict[str, Any]]:
    index = load_index()
    return {str(item.get("title_id", item.get("id", ""))): item for item in index.get("titles", []) if item.get("title_id", item.get("id"))}


def get_title(title_id: str) -> dict[str, Any] | None:
    return title_map().get(str(title_id))
