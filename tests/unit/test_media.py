from io import BytesIO
from pathlib import Path
import pytest
from PIL import Image
from app.services.media import UnsupportedMedia, detect_kind, dhash, hamming_distance, validate_image_bytes


def png_bytes(color=(20, 30, 40)):
    image = Image.new("RGB", (48, 48), color=color)
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_detect_supported_kinds():
    assert detect_kind("frame.PNG", "image/png") == "image"
    assert detect_kind("clip.mp4", "video/mp4") == "video"
    assert detect_kind("clip.mov", "application/octet-stream") == "video"


def test_rejects_extension_mime_mismatch():
    with pytest.raises(UnsupportedMedia):
        detect_kind("payload.exe", "application/octet-stream")
    with pytest.raises(UnsupportedMedia):
        detect_kind("frame.png", "video/mp4")


def test_validates_real_image_content():
    width, height = validate_image_bytes(png_bytes())
    assert (width, height) == (48, 48)
    with pytest.raises(UnsupportedMedia):
        validate_image_bytes(b"not really a PNG")


def test_dhash_and_hamming_distance_are_stable():
    image = Image.open(BytesIO(png_bytes()))
    first = dhash(image)
    second = dhash(image.copy())
    assert first == second
    assert hamming_distance(first, second) == 0
    assert hamming_distance(0, 2**64 - 1) == 64
