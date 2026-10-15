FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
ENV PYTHONPATH=/app:/app/worker
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
COPY apps/api/requirements.txt /app/requirements.txt
RUN pip install --upgrade pip && pip install -r /app/requirements.txt
COPY apps/api /app
COPY apps/worker /app/worker
RUN mkdir -p /data/uploads /data/reference /data/reports
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --fake-initial && gunicorn sceneseek_project.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120"]
