"""Run the recognition worker in the foreground: ``python manage.py runworker``."""
import asyncio
import logging

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Process queued identification jobs (run next to `runserver`, or rely on the embedded worker)."

    def handle(self, *args, **options):
        logging.getLogger().setLevel(settings.LOG_LEVEL)
        from worker.loop import serve
        self.stdout.write(self.style.SUCCESS("SceneSeek worker started. Press Ctrl+C to stop."))
        try:
            asyncio.run(serve())
        except KeyboardInterrupt:
            self.stdout.write("Worker stopped.")
