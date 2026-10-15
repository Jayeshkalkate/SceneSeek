import logging
import os
import threading

from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sceneseek_project.settings")
application = get_wsgi_application()

logger = logging.getLogger("sceneseek.worker")
_worker_started = False


def _start_embedded_worker() -> None:
    """Run the queue consumer inside the web process (Render free tier / local SQLite dev)."""
    global _worker_started
    if _worker_started:
        return
    _worker_started = True

    def _run() -> None:
        import asyncio
        try:
            from worker.loop import serve
            asyncio.run(serve())
        except Exception:  # never take the web server down because the worker failed to start
            logger.exception("Embedded worker stopped unexpectedly")

    threading.Thread(target=_run, name="sceneseek-worker", daemon=True).start()
    logger.info("Embedded worker thread started")


from django.conf import settings  # noqa: E402

if settings.RUN_EMBEDDED_WORKER:
    _start_embedded_worker()
