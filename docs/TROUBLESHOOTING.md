# Troubleshooting

## `sqlite3.OperationalError: unable to open database file` on `migrate`
**Cause (fixed in this version):** with no `DATABASE_URL`, the old settings pointed SQLite at `/data/sceneseek.db`,
a Linux/Docker path that does not exist on Windows. SceneSeek now defaults to `<repo>/data/sceneseek.db`
(created automatically) on every OS. A blank `DATABASE_URL=` or the unedited placeholder from `.env.example`
is also treated as "use the default".

## `can't open file '...\sceneseek\manage.py'`
`manage.py` now exists at the repo root as well as in `apps/api`; both work.

## `table "jobs" already exists`
You have a database created by the earlier SQLAlchemy version. `python manage.py migrate` now records the
initial migration automatically (`--fake-initial` is built in), so just run it again.

## Uploads stay "queued" forever
No worker is running. On SQLite the worker is embedded in `runserver` automatically; on PostgreSQL either set
`RUN_EMBEDDED_WORKER=true` (Render free) or run `python manage.py runworker` / the Docker `worker` service.
Check `http://localhost:8000/healthz` for `queue_depth` and `worker`.

## `429 Too many requests`
Uploads are limited to `API_RATE_LIMIT_PER_MINUTE` (default 10) per IP and other API calls to
`READ_RATE_LIMIT_PER_MINUTE` (default 180). Set `RATE_LIMIT_ENABLED=false` for load tests.

## Browser shows a CORS error
Set `CORS_ORIGINS` to the exact UI origin (scheme + host + port, no trailing slash), e.g. `http://localhost:3000`.

## Running `sceneseek_project/settings.py` as a command
That file is Python code, not a script - Git Bash then prints `import: command not found`. Use `python manage.py ...`.

## `ImproperlyConfigured: Set DJANGO_SECRET_KEY`
Raised when `APP_ENV=production` or `GOOGLE_CLIENT_ID` is set without a real secret. Generate one:
`python -c "import secrets;print(secrets.token_hex(32))"`.
