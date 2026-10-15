from __future__ import annotations
import logging
import re
import subprocess
from pathlib import Path
from typing import Any
from app.config import get_settings
from app.services.media import UnsupportedMedia

logger = logging.getLogger(__name__)
TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOPWORDS = {"the", "and", "you", "are", "was", "were", "that", "this", "with", "from", "have", "has", "not", "but", "for", "all", "your", "his", "her", "they", "them", "its", "into", "then", "than", "what", "when", "who", "why", "how", "can", "could", "would", "will", "just", "like", "about", "there", "their", "been", "get", "got", "out", "one", "two", "she", "him", "our", "youre", "im"}


def tokenize(text: str) -> set[str]:
    return {token.lower() for token in TOKEN.findall(text or "") if len(token) > 2 and token.lower() not in STOPWORDS}


def extract_ocr(paths: list[Path]) -> str:
    if not get_settings().enable_ocr:
        return ""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        logger.warning("OCR is enabled but its optional dependency is missing")
        return ""
    chunks: list[str] = []
    for path in paths:
        try:
            with Image.open(path) as image:
                text = pytesseract.image_to_string(image.convert("RGB"), timeout=6)
            text = " ".join(text.split())
            if len(text) >= 2:
                chunks.append(text)
        except Exception:
            logger.info("OCR was skipped for a frame")
    return " ".join(chunks)[:2000]


def transcribe_video(video_path: Path, work_dir: Path) -> str:
    if not get_settings().enable_asr:
        return ""
    audio = work_dir / "audio.wav"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(video_path),
             "-t", "30", "-vn", "-ac", "1", "-ar", "16000", "-f", "wav", str(audio)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=45,
        )
        if proc.returncode != 0 or not audio.exists() or audio.stat().st_size == 0:
            return ""
        from faster_whisper import WhisperModel
        transcript_model = _asr_model()
        segments, _ = transcript_model.transcribe(str(audio), beam_size=1, vad_filter=True)
        return " ".join(segment.text.strip() for segment in segments)[:2000]
    except ImportError:
        logger.warning("ASR is enabled but faster-whisper is not installed")
        return ""
    except Exception:
        logger.exception("ASR failed; visual matching will continue")
        return ""


_ASR_MODEL = None


def _asr_model():
    global _ASR_MODEL
    if _ASR_MODEL is None:
        from faster_whisper import WhisperModel
        _ASR_MODEL = WhisperModel("base", device="cpu", compute_type="int8")
    return _ASR_MODEL


def calculate_text_scores(query_text: str, titles: list[dict[str, Any]]) -> dict[str, float]:
    query_tokens = tokenize(query_text)
    if not query_tokens:
        return {}
    scores: dict[str, float] = {}
    for title in titles:
        title_id = str(title.get("title_id", title.get("id", "")))
        if not title_id:
            continue
        name_tokens = tokenize(" ".join([str(title.get("title") or ""), str(title.get("original_title") or "")]))
        synopsis_tokens = tokenize(str(title.get("synopsis") or ""))
        name_overlap = len(query_tokens & name_tokens) / max(1, len(name_tokens))
        synopsis_overlap = len(query_tokens & synopsis_tokens) / max(1, len(query_tokens))
        score = min(1.0, max(name_overlap * 2.0, synopsis_overlap))
        if score > 0:
            scores[title_id] = round(score, 4)
    return scores
