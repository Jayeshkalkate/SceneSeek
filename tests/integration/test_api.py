import io
import os
import pytest
from django.test import Client
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sceneseek_project.settings")

@pytest.fixture
def client():
    return Client()

def image_bytes():
    image = Image.new("RGB", (64, 64), color=(15, 70, 180))
    stream = io.BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()

@pytest.mark.django_db
def test_ping_and_health(client):
    assert client.get("/ping").status_code == 200
    response = client.get("/healthz")
    assert response.status_code == 200
    assert "db" in response.json()
    assert client.head("/ping").status_code == 200

@pytest.mark.django_db
def test_reference_status_shape(client):
    response = client.get("/v1/reference/status")
    assert response.status_code == 200
    assert "ready" in response.json()

@pytest.mark.django_db
def test_upload_creates_job_and_duplicate_is_idempotent(client, settings, tmp_path, monkeypatch):
    # Isolate local upload storage and bypass external object storage.
    monkeypatch.setattr("core.views.store_upload", lambda data, key, mime: f"local://{key}")
    monkeypatch.setattr("core.views.delete_upload", lambda uri: None)
    response = client.post("/v1/identify", {"file": SimpleUploadedFile("sample.png", image_bytes(), content_type="image/png")})
    assert response.status_code == 202, response.content
    job_id = response.json()["job_id"]
    assert response.json()["status"] == "queued"
    state = client.get(f"/v1/jobs/{job_id}")
    assert state.status_code == 200
    assert state.json()["status"] == "queued"
    duplicate = client.post("/v1/identify", {"file": SimpleUploadedFile("sample.png", image_bytes(), content_type="image/png")})
    assert duplicate.status_code == 202
    assert duplicate.json()["job_id"] == job_id

@pytest.mark.django_db
def test_unsupported_upload_rejected(client):
    response = client.post("/v1/identify", {"file": SimpleUploadedFile("script.exe", b"nope", content_type="application/octet-stream")})
    assert response.status_code in (400, 415)

@pytest.mark.django_db
def test_auth_required_for_me(client):
    response = client.get("/v1/me")
    assert response.status_code == 401
