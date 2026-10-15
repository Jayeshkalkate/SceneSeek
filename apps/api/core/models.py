from django.db import models
from django.utils import timezone

class Job(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    status = models.CharField(max_length=16, default="queued")
    input_kind = models.CharField(max_length=8)
    input_path = models.TextField(null=True, blank=True)
    mime = models.CharField(max_length=120)
    bytes = models.IntegerField()
    sha256 = models.CharField(max_length=64, db_index=True)
    attempts = models.IntegerField(default=0)
    max_attempts = models.IntegerField(default=3)
    user_id = models.CharField(max_length=36, null=True, blank=True, db_index=True)
    error = models.TextField(null=True, blank=True)
    result = models.JSONField(null=True, blank=True)
    latency_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    class Meta:
        db_table = "jobs"
        indexes = [models.Index(fields=["status", "created_at"], name="ix_jobs_status_created")]

class Feedback(models.Model):
    id = models.AutoField(primary_key=True)
    job = models.ForeignKey(Job, null=True, blank=True, on_delete=models.SET_NULL, db_column="job_id")
    predicted_title_id = models.CharField(max_length=128, null=True, blank=True)
    correct_title_id = models.CharField(max_length=128, null=True, blank=True)
    verdict = models.CharField(max_length=16)
    note = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        db_table = "feedback"

class TakedownRequest(models.Model):
    id = models.AutoField(primary_key=True)
    source_url = models.TextField()
    reason = models.TextField()
    contact_email = models.CharField(max_length=320, null=True, blank=True)
    status = models.CharField(max_length=16, default="open")
    created_at = models.DateTimeField(default=timezone.now)
    class Meta:
        db_table = "takedown_requests"

class MetadataCache(models.Model):
    title_id = models.CharField(max_length=128, primary_key=True)
    data = models.JSONField()
    fetched_at = models.DateTimeField(default=timezone.now)
    class Meta:
        db_table = "metadata_cache"

class User(models.Model):
    id = models.CharField(max_length=36, primary_key=True)
    google_sub = models.CharField(max_length=64, unique=True, db_index=True)
    email = models.CharField(max_length=320)
    name = models.CharField(max_length=200, null=True, blank=True)
    picture = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(default=timezone.now)
    class Meta:
        db_table = "users"
