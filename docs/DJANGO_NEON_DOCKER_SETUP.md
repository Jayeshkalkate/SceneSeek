# SceneSeek — Django + Neon + Docker

The web API has been migrated to Django. The Next.js UI and the existing recognition worker/pipeline are retained so the visual-identification logic is not thrown away. The API and worker both use Django ORM against the same PostgreSQL queue tables. Both services must use the same `DATABASE_URL`.

## Requirements
- Python 3.12+
- Docker Desktop (recommended for local setup)
- A Neon PostgreSQL database and its pooled or direct connection string

## Configure
1. Copy `.env.example` to `.env`.
2. Set `DATABASE_URL` to the Neon connection string. Keep `sslmode=require`; for Neon, use the provider's connection string and do not commit it.
3. Set `DJANGO_SECRET_KEY` and `JWT_SECRET` to long random values.
4. Set `CORS_ORIGINS` to your exact frontend origin and `NEXT_PUBLIC_API_URL` to your API URL.
5. If using Google login, configure `GOOGLE_CLIENT_ID` in both the provider console and `.env`.

## Run with Docker
```bash
docker compose up --build
```
- Web UI: http://localhost:3000
- Django API: http://localhost:8000
- Health: http://localhost:8000/healthz

## Run the API locally
```bash
cd apps/api
python -m venv .venv
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python manage.py check
python manage.py migrate --fake-initial
python manage.py runserver 0.0.0.0:8000
```

`python manage.py makemigrations core` is the Django migration command. Do not run `makemigrations` against the repository root; `manage.py` is under `apps/api/`.

## Database notes
- `DATABASE_URL` should be the Neon PostgreSQL URL; PostgreSQL connections use SSL by default.
- The worker and API share `jobs`, `users`, `feedback`, `metadata_cache`, and `takedown_requests`. Django models live in `apps/api/core/models.py` and are used by both API and worker.
- A checked-in initial Django migration is included. Startup uses `migrate --fake-initial` so an existing database whose tables were created by the prior SQLAlchemy worker can be recognized as already initialized. Review the schema before applying this to any production database.
- Back up Neon before running schema changes against an existing production database. Never point a fresh schema migration at a production database without checking existing tables first.

## Deployment
Render uses `Dockerfile.render` for the Django API and `apps/web/Dockerfile` for Next.js. Configure `DATABASE_URL`, `JWT_SECRET`, `DJANGO_SECRET_KEY`, `CORS_ORIGINS`, `GOOGLE_CLIENT_ID`, and the frontend's `NEXT_PUBLIC_API_URL` in Render environment settings. Ensure `FRONTEND_URL` is the actual deployed frontend URL.

## Operational notes
- Rate limiting should be enforced at the edge/proxy for production; the API container does not use a distributed rate-limit store yet.
- Do not expose the worker-status file or uploaded files as public static assets.
- Configure an object-storage backend for multi-instance production; local upload paths are suitable only when API and worker share the same volume.

## Recognition quality
A successful deployment does not mean the reference index is populated. Prepare a lawful reference index and evaluation labels using the tools in `tools/`. Online anime/title lookups are supplemental and do not guarantee every screenshot or reel can be identified.
