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


def _login_token(user_id):
    from app.auth import create_token
    return create_token(user_id)


@pytest.fixture
def user(db):
    from core.models import User
    return User.objects.create(id="user-1", google_sub="sub-1", email="a@example.com", name="Ann")


@pytest.mark.django_db
def test_unknown_route_returns_json_404(client):
    response = client.get("/v1/does-not-exist")
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.django_db
def test_public_config_exposes_limits(client):
    data = client.get("/v1/config").json()
    assert data["max_image_mb"] >= 1 and data["max_video_seconds"] >= 1


@pytest.mark.django_db
def test_job_visible_to_owner_only_and_history_delete(client, user, monkeypatch):
    from core.models import Job
    token = _login_token(user.id)
    Job.objects.create(id="job-owned", status="done", input_kind="image", mime="image/png", bytes=10,
                       sha256="a" * 64, user_id=user.id, result={"candidates": [{"title": "X", "title_id": "t1"}], "band": "low"})
    assert client.get("/v1/jobs/job-owned").status_code == 404
    ok = client.get("/v1/jobs/job-owned", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert ok.status_code == 200
    history = client.get("/v1/me/history", HTTP_AUTHORIZATION=f"Bearer {token}").json()["items"]
    assert history[0]["title"] == "X"
    assert client.delete("/v1/me/history/job-owned").status_code == 401
    deleted = client.delete("/v1/me/history/job-owned", HTTP_AUTHORIZATION=f"Bearer {token}")
    assert deleted.status_code == 200 and not Job.objects.filter(pk="job-owned").exists()


@pytest.mark.django_db
def test_delete_account_removes_everything(client, user):
    from core.models import Job, User
    Job.objects.create(id="j2", status="done", input_kind="image", mime="image/png", bytes=1, sha256="b" * 64, user_id=user.id)
    response = client.delete("/v1/me/delete", HTTP_AUTHORIZATION=f"Bearer {_login_token(user.id)}")
    assert response.status_code == 200
    assert not User.objects.filter(pk=user.id).exists() and not Job.objects.filter(user_id=user.id).exists()


@pytest.mark.django_db
def test_feedback_and_takedown_validation(client):
    from core.models import Job
    Job.objects.create(id="j3", status="done", input_kind="image", mime="image/png", bytes=1, sha256="c" * 64)
    post = lambda path, body: client.post(path, body, content_type="application/json")
    assert post("/v1/feedback", {"job_id": "j3", "verdict": "correct"}).status_code == 201
    assert post("/v1/feedback", {"job_id": "j3", "verdict": "maybe"}).status_code == 400
    assert post("/v1/feedback", {"job_id": "j3", "verdict": "wrong", "note": "x" * 2000}).status_code == 400
    assert post("/v1/takedown", {"source_url": "ftp://x", "reason": "long enough reason"}).status_code == 400
    assert post("/v1/takedown", {"source_url": "https://x.example/a", "reason": "short"}).status_code == 400
    assert post("/v1/takedown", {"source_url": "https://x.example/a", "reason": "long enough reason", "contact_email": "bad"}).status_code == 400
    assert post("/v1/takedown", {"source_url": "https://x.example/a", "reason": "long enough reason", "contact_email": "me@example.com"}).status_code == 202


@pytest.mark.django_db
def test_rate_limit_returns_429(client, settings):
    settings.RATE_LIMIT_ENABLED = True
    settings.READ_RATE_LIMIT_PER_MINUTE = 3
    codes = [client.get("/v1/reference/status", REMOTE_ADDR="9.9.9.9").status_code for _ in range(5)]
    assert codes[:3] == [200, 200, 200] and codes[3] == 429
    limited = client.get("/v1/reference/status", REMOTE_ADDR="9.9.9.9")
    assert limited["Retry-After"]


@pytest.mark.django_db
def test_cors_headers_for_allowed_origin(client, settings):
    settings.CORS_ORIGINS = ["http://localhost:3000"]
    response = client.get("/ping", HTTP_ORIGIN="http://localhost:3000")
    assert response["Access-Control-Allow-Origin"] == "http://localhost:3000"
    assert "X-Request-ID" in response
