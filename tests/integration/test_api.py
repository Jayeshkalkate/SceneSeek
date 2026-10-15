from io import BytesIO
from fastapi.testclient import TestClient
from PIL import Image
from app.main import app
from app.database import SessionLocal
from app.models import Job
from app.services.storage import delete_upload


def image_bytes():
    image = Image.new("RGB", (64, 64), color=(15, 70, 180))
    stream = BytesIO()
    image.save(stream, format="PNG")
    return stream.getvalue()


def test_health_and_reference_status():
    with TestClient(app) as client:
        health = client.get("/healthz")
        assert health.status_code == 200
        assert health.json()["db"] is True
        index = client.get("/v1/reference/status")
        assert index.status_code == 200
        assert "ready" in index.json()


def test_upload_creates_a_queued_job_and_is_idempotent():
    with TestClient(app) as client:
        files = {"file": ("sample.png", image_bytes(), "image/png")}
        first = client.post("/v1/identify", files=files)
        assert first.status_code == 202, first.text
        job_id = first.json()["job_id"]
        assert first.json()["status"] == "queued"
        state = client.get(f"/v1/jobs/{job_id}")
        assert state.status_code == 200
        assert state.json()["status"] == "queued"

        duplicate = client.post("/v1/identify", files={"file": ("sample.png", image_bytes(), "image/png")})
        assert duplicate.status_code == 202
        assert duplicate.json()["job_id"] == job_id

        with SessionLocal() as db:
            job = db.get(Job, job_id)
            assert job is not None
            uri = job.input_path
            db.delete(job)
            db.commit()
        delete_upload(uri)


def test_unsupported_upload_is_rejected():
    with TestClient(app) as client:
        response = client.post("/v1/identify", files={"file": ("script.exe", b"nope", "application/octet-stream")})
        assert response.status_code == 415
