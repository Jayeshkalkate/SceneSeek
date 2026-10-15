import os
import threading
import asyncio
from django.core.wsgi import get_wsgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sceneseek_project.settings")
application = get_wsgi_application()

# Render's free blueprint deploys the API and UI only. Run the queue consumer
# in the API container there; Compose sets RUN_EMBEDDED_WORKER=false and runs
# a dedicated worker container instead.
if os.getenv("RUN_EMBEDDED_WORKER", "false").lower() == "true":
    def _run_worker():
        from worker.loop import serve
        asyncio.run(serve())
    threading.Thread(target=_run_worker, name="sceneseek-worker", daemon=True).start()
