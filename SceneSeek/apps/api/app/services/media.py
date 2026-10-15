from __future__ import annotations
import hashlib
import io
import json
import subprocess
from pathlib import Path
from PIL import Image, ImageOps

IMAGE_MIMES = {".jpg": {"image/jpeg"}, ".jpeg": {"image/jpeg"}, ".png": {"image/png"}, ".webp": {"image/webp"}}
VIDEO_MIMES = {
    ".mp4": {"video/mp4", "application/mp4"},
    ".webm": {"video/webm"},
    ".mov": {"video/quicktime", "video/mp4"},
}
ALLOWED_VIDEO_CODECS = {"h264", "hevc", "vp8", "vp9", "av1", "mpeg4"}


class UnsupportedMedia(ValueError):
    pass


def detect_kind(filename: str, mime: str) -> str:
    suffix = Path(filename or "").suffix.lower()
    mime = (mime or "application/octet-stream").split(";", 1)[0].strip().lower()
    if suffix in IMAGE_MIMES and (mime in IMAGE_MIMES[suffix] or mime in {"", "application/octet-stream"}):
        return "image"
    if suffix in VIDEO_MIMES and (mime in VIDEO_MIMES[suffix] or mime in {"", "application/octet-stream"}):
        return "video"
    raise UnsupportedMedia("Unsupported file type. Upload JPG, PNG, WebP, MP4, WebM, or MOV.")


def validate_image_bytes(data: bytes) -> tuple[int, int]:
    try:
        with Image.open(io.BytesIO(data)) as img:
            if img.format not in {"JPEG", "PNG", "WEBP"}:
                raise UnsupportedMedia("The uploaded image format is not supported.")
            width, height = img.size
            if width < 16 or height < 16:
                raise UnsupportedMedia("The image is too small to identify.")
            if width * height > 40_000_000:
                raise UnsupportedMedia("The image is too large to process safely (maximum 40 megapixels).")
            img.verify()
        return width, height
    except UnsupportedMedia:
        raise
    except Exception as exc:
        raise UnsupportedMedia("The uploaded image is corrupt or cannot be decoded.") from exc


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def probe_video(path: Path, max_seconds: int) -> dict:
    """Validate the actual video container/codec, not merely its filename or MIME header."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=20,
        )
    except FileNotFoundError as exc:
        raise UnsupportedMedia("FFprobe is required for video uploads. Install FFmpeg and retry.") from exc
    except subprocess.TimeoutExpired as exc:
        raise UnsupportedMedia("Video validation timed out. Try a shorter clip.") from exc
    if proc.returncode != 0:
        raise UnsupportedMedia("The video is corrupt or uses an unsupported container.")
    try:
        info = json.loads(proc.stdout)
        duration = float(info.get("format", {}).get("duration") or 0)
        streams = info.get("streams", [])
        video = next((stream for stream in streams if stream.get("codec_type") == "video"), None)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise UnsupportedMedia("Could not read the video metadata.") from exc
    if not video or video.get("codec_name") not in ALLOWED_VIDEO_CODECS:
        raise UnsupportedMedia("The video has no supported video stream.")
    if duration <= 0:
        raise UnsupportedMedia("The clip duration could not be determined.")
    if duration > max_seconds + 0.5:
        raise UnsupportedMedia(f"Video clips must be {max_seconds} seconds or shorter.")
    width, height = int(video.get("width") or 0), int(video.get("height") or 0)
    if width < 16 or height < 16 or width * height > 40_000_000:
        raise UnsupportedMedia("The video dimensions are unsupported or too large to process safely.")
    return {"duration": duration, "width": width, "height": height, "codec": video.get("codec_name")}


def prepare_image(path: Path, max_width: int = 1024) -> Image.Image:
    with Image.open(path) as original:
        img = ImageOps.exif_transpose(original).convert("RGB")
        if img.width > max_width:
            height = max(1, round(img.height * max_width / img.width))
            img = img.resize((max_width, height), Image.Resampling.LANCZOS)
        return img.copy()


def dhash(image: Image.Image) -> int:
    """64-bit difference hash, implemented locally to avoid an extra runtime dependency."""
    gray = ImageOps.grayscale(image).resize((9, 8), Image.Resampling.LANCZOS)
    pixels = list(gray.tobytes())
    value = 0
    for y in range(8):
        offset = y * 9
        for x in range(8):
            value = (value << 1) | int(pixels[offset + x] > pixels[offset + x + 1])
    return value


def hamming_distance(a: int, b: int) -> int:
    return (a ^ b).bit_count()


def extract_video_frames(video_path: Path, output_dir: Path, duration: float) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    fps = 1.0 if duration <= 15 else 0.5
    pattern = output_dir / "frame_%03d.jpg"
    vf = f"fps={fps},scale='min(720,iw)':-2"
    try:
        proc = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-i", str(video_path),
             "-vf", vf, "-frames:v", "12", "-q:v", "3", str(pattern)],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False, timeout=90,
        )
    except FileNotFoundError as exc:
        raise UnsupportedMedia("FFmpeg is required for video uploads. Install FFmpeg and retry.") from exc
    except subprocess.TimeoutExpired as exc:
        raise UnsupportedMedia("Frame extraction took too long. Try a shorter or smaller clip.") from exc
    if proc.returncode != 0:
        raise UnsupportedMedia("Could not extract frames from this video.")
    frames = sorted(output_dir.glob("frame_*.jpg"))
    if not frames:
        raise UnsupportedMedia("No usable frames were found in this clip.")
    return frames


def dedupe_paths(paths: list[Path], threshold: int = 6) -> list[Path]:
    kept: list[Path] = []
    hashes: list[int] = []
    for path in paths:
        try:
            with Image.open(path) as img:
                value = dhash(img.convert("RGB"))
        except Exception:
            continue
        if any(hamming_distance(value, old) <= threshold for old in hashes):
            continue
        kept.append(path)
        hashes.append(value)
    return kept[:12] or paths[:1]
