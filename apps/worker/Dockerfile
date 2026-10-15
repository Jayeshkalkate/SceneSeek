FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY apps/api/requirements.txt /app/apps/api/requirements.txt
COPY apps/worker/requirements.txt /app/apps/worker/requirements.txt
COPY apps/worker/requirements-clip.txt /app/apps/worker/requirements-clip.txt
COPY apps/worker/requirements-ocr.txt /app/apps/worker/requirements-ocr.txt
COPY apps/worker/requirements-asr.txt /app/apps/worker/requirements-asr.txt
RUN pip install --no-cache-dir -r /app/apps/worker/requirements.txt
ARG INSTALL_CLIP=false
ARG INSTALL_OCR=false
ARG INSTALL_ASR=false
RUN if [ "$INSTALL_CLIP" = "true" ]; then pip install --no-cache-dir -r /app/apps/worker/requirements-clip.txt; fi
RUN if [ "$INSTALL_OCR" = "true" ]; then apt-get update && apt-get install -y --no-install-recommends tesseract-ocr && rm -rf /var/lib/apt/lists/* && pip install --no-cache-dir -r /app/apps/worker/requirements-ocr.txt; fi
RUN if [ "$INSTALL_ASR" = "true" ]; then pip install --no-cache-dir -r /app/apps/worker/requirements-asr.txt; fi
COPY apps/api/app /app/apps/api/app
COPY apps/api/core /app/core
COPY apps/api/sceneseek_project /app/sceneseek_project
COPY apps/worker/worker /app/apps/worker/worker
ENV PYTHONPATH=/app:/app/apps/api:/app/apps/worker DJANGO_SETTINGS_MODULE=sceneseek_project.settings
RUN mkdir -p /data/uploads /data/reference
CMD ["python", "-m", "worker.main"]
