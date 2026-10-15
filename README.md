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

## Quick start
1. Copy `.env.example` to `.env`.
2. Replace `DATABASE_URL` with your Neon PostgreSQL connection string and keep `sslmode=require`.
3. Set `DJANGO_SECRET_KEY` and `JWT_SECRET` to long random secrets.
4. Run:
   ```bash
   docker compose up --build
   ```
5. Open:
   - Frontend: http://localhost:3000
   - API health: http://localhost:8000/healthz

For local Python setup, migration instructions, Neon configuration, and Render deployment, see [`docs/DJANGO_NEON_DOCKER_SETUP.md`](docs/DJANGO_NEON_DOCKER_SETUP.md).

## Useful commands
```bash
cd apps/api
pip install -r requirements-dev.txt
python manage.py check
python manage.py makemigrations core
python manage.py migrate --fake-initial
python manage.py runserver 0.0.0.0:8000
```

## Important recognition limitation
SceneSeek is a closed-set visual search system. It can only reliably match titles represented in the prepared reference index. Online metadata search is supplemental and is not the same as identifying a scene. Build a lawfully sourced reference index and evaluate it against labeled, held-out examples before claiming accuracy.

## Safety and operations
- Do not commit `.env` or expose database credentials.
- Configure `CORS_ORIGINS` to the exact frontend origin.
- Keep uploads private and temporary; use shared object storage for multi-instance deployments.
- Review the privacy, legal, takedown, and deployment notes in `docs/`.
