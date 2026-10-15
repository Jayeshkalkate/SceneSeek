# Changelog

## 2.0 - stabilisation release
**Fixes**
- `migrate` failed with *unable to open database file*: SQLite default pointed at `/data/...` (Linux-only). Paths now resolve under the repo (`app/env.py`), directories are auto-created, `.env` is loaded, blank/placeholder `DATABASE_URL` falls back to SQLite.
- API and worker could silently use two different databases when `DATABASE_URL` was unset; both now share one normalised URL.
- Signed-in users' searches always failed (job polling and feedback requests omitted the auth header, so the API returned 404).
- Upload filenames containing Windows backslashes were not stripped (wrong escape).
- Plain `migrate` crashed on databases created by the old SQLAlchemy version; `migrate` now adopts them automatically.
- Makefile still referenced the removed FastAPI app; CI called `pip-audit` without installing it; Docker image ignored `$PORT`.
- Worker thread leaked a DB connection per pool thread; it now uses one dedicated thread with proper connection cleanup and exponential back-off.
- 404/500 responses are JSON; CORS headers are now also sent on error responses.

**New**
- Rate limiting (uploads and reads), request IDs, JSON error handlers, stricter input validation (feedback, takedown).
- History: delete one search, clear all, delete account (`DELETE /v1/me/...`); title detail pages for search results (TVmaze/iTunes ids).
- Queue position in job status; server-driven upload limits via `/v1/config`.
- `manage.py runworker` and `manage.py cleanup` commands; root-level `manage.py`.
- Web: paste screenshots (Ctrl+V), cancel/retry, auto-retry on cold starts, queue/elapsed indicator, keyboard/a11y improvements, skip link, error/404/loading pages, shared header/footer/API client.
- More tests (config, history, validation, rate-limit, CORS) and `docs/TROUBLESHOOTING.md`.
