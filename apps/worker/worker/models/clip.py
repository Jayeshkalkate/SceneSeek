from __future__ import annotations
from functools import lru_cache
from threading import Lock
from pathlib import Path
from PIL import Image

_model_lock = Lock()


@lru_cache(maxsize=1)
def get_model(model_name: str):
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError("This index uses CLIP embeddings. Install apps/worker/requirements-clip.txt.") from exc
    model = SentenceTransformer(model_name, device="cpu")
    model.eval()
    return model


def embed_images(paths: list[Path], model_name: str):
    model = get_model(model_name)
    images = []
    try:
        for path in paths:
            with Image.open(path) as image:
                images.append(image.convert("RGB").copy())
        with _model_lock:
            vectors = model.encode(images, batch_size=8, convert_to_numpy=True,
                                   normalize_embeddings=True, show_progress_bar=False)
        return vectors
    finally:
        for image in images:
            image.close()
