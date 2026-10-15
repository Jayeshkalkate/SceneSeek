#!/bin/sh
set -eu
python manage.py migrate --fake-initial
exec gunicorn sceneseek_project.wsgi:application --bind 0.0.0.0:8000 --workers "${WEB_CONCURRENCY:-2}" --timeout 120
