"""Housekeeping: ``python manage.py cleanup`` removes expired uploads, old jobs and stale cache rows."""
import os
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Delete expired uploads, finished jobs older than --days, and stale metadata cache."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=30, help="Keep finished anonymous jobs this long (default 30).")

    def handle(self, *args, **options):
        from app.services.storage import cleanup_local_uploads, delete_upload
        from core.models import Job, MetadataCache

        ttl_hours = int(os.getenv("UPLOAD_TTL_HOURS", "24"))
        files = cleanup_local_uploads(ttl_hours * 3600)
        cutoff = timezone.now() - timedelta(days=max(1, options["days"]))
        old = Job.objects.filter(status__in=["done", "failed"], user_id__isnull=True, created_at__lt=cutoff)
        for job in old.exclude(input_path__isnull=True):
            delete_upload(job.input_path)
        jobs, _ = old.delete()
        cache, _ = MetadataCache.objects.filter(fetched_at__lt=timezone.now() - timedelta(days=7)).delete()
        self.stdout.write(self.style.SUCCESS(f"Removed {files} file(s), {jobs} job row(s), {cache} cache row(s)."))
