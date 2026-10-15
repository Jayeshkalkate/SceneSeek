#!/bin/sh
# Container entrypoint: apply migrations (legacy tables are recognised automatically), then serve.
set -eu
python manage.py migrate --noinput
exec gunicorn sceneseek_project.wsgi:application \
  --bind "0.0.0.0:${PORT:-8000}" \
  --workers "${WEB_CONCURRENCY:-2}" \
  --threads "${GUNICORN_THREADS:-4}" \
  --timeout "${GUNICORN_TIMEOUT:-120}" \
  --access-logfile - --error-logfile -
