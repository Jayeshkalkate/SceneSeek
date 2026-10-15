# SceneSeek

**See it. Seek it. Find it.**

SceneSeek helps identify movies, series, and anime from screenshots or short video clips.

## Technology stack
- **Backend API:** Python + Django
- **Database:** Neon PostgreSQL (SQLite can be used for local-only development)
- **Containerization:** Docker Compose
- **Frontend:** Next.js / React
- **Recognition worker:** Python worker with a persistent database-backed job queue
- **Recognition pipeline:** visual frame matching plus optional OCR/audio signals and online metadata lookups

The Django API and worker share the same database tables. The API and worker both use Django ORM; queue claiming is transactional and uses PostgreSQL row locks with SKIP LOCKED. The frontend and recognition pipeline are preserved from the prior version; this migration changes the active API framework.

## Quick start (local, no Docker, no database setup)
```bash
python -m pip install -r apps/api/requirements-dev.txt
python manage.py migrate          # works from the repo root; creates data/sceneseek.db (SQLite)
python manage.py runserver        # API on http://127.0.0.1:8000 (worker runs inside it)

cd apps/web && npm install && npm run dev   # UI on http://localhost:3000
```
No `.env` is required. To customise, copy `.env.example` to `.env` (repo root). Leave `DATABASE_URL`
commented out for SQLite, or paste your Neon connection string to use PostgreSQL.

`python manage.py runworker` starts a standalone worker (set `RUN_EMBEDDED_WORKER=false` first),
and `python manage.py cleanup` removes expired uploads and old jobs.

## Quick start (Docker + Neon)
1. Copy `.env.example` to `.env`, set `DATABASE_URL` (Neon, `sslmode=require`), `DJANGO_SECRET_KEY`, `JWT_SECRET`.
2. `docker compose up --build`
3. Frontend http://localhost:3000 - API health http://localhost:8000/healthz

See [`docs/DJANGO_NEON_DOCKER_SETUP.md`](docs/DJANGO_NEON_DOCKER_SETUP.md) and [`docs/TROUBLESHOOTING.md`](docs/TROUBLESHOOTING.md).

## Useful commands
```bash
python manage.py check                 # run from the repo root or apps/api
python manage.py makemigrations core   # only after editing apps/api/core/models.py
python manage.py migrate               # also adopts databases created by the old SQLAlchemy version
python -m pytest -q                    # full test-suite
make setup | api | web | test          # shortcuts (see Makefile)
```

## Important recognition limitation
SceneSeek is a closed-set visual search system. It can only reliably match titles represented in the prepared reference index. Online metadata search is supplemental and is not the same as identifying a scene. Build a lawfully sourced reference index and evaluate it against labeled, held-out examples before claiming accuracy.

## Safety and operations
- Do not commit `.env` or expose database credentials.
- Configure `CORS_ORIGINS` to the exact frontend origin.
- Keep uploads private and temporary; use shared object storage for multi-instance deployments.
- Review the privacy, legal, takedown, and deployment notes in `docs/`.
