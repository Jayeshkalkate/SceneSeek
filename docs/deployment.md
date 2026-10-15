# Deployment: Neon + Render + UptimeRobot + Google sign-in (all free)

Free plans change; check current limits before launch.

## 1. Neon (PostgreSQL)
1. Create a project at neon.tech. Copy the **pooled** connection string (host contains `-pooler`), ending in `?sslmode=require`.
2. That is your `DATABASE_URL`. Tables are created automatically on first start. (Existing databases created from an older version need the new `users` table and `jobs.user_id` column: drop the old tables or run `ALTER TABLE jobs ADD COLUMN user_id varchar(36);`.)
3. Neon suspends idle compute; the app recycles connections and retries via `pool_pre_ping`, so the first request after idle is just slower.

## 2. Google sign-in
1. Google Cloud Console → APIs & Services → Credentials → Create **OAuth client ID** → *Web application*.
2. Authorized JavaScript origins: `http://localhost:3000` and your Render web URL (e.g. `https://sceneseek-web.onrender.com`). No redirect URI is needed (Google Identity Services button).
3. Put the client ID in the API's `GOOGLE_CLIENT_ID` and set `JWT_SECRET` (Render generates one from `render.yaml`). The frontend reads the client ID from `/v1/config`, so no rebuild is needed.
4. Sign-in is optional by default (history of past searches). Set `REQUIRE_LOGIN=true` to require it for uploads.

## 3. Render
1. Push this repo to GitHub → Render → **New → Blueprint** → select the repo (`render.yaml`).
2. Fill the prompted env vars: API `DATABASE_URL`, `GOOGLE_CLIENT_ID`, `CORS_ORIGINS` (the web URL); web `NEXT_PUBLIC_API_URL` (the API URL). Deploy API first, then set the web URL into `CORS_ORIGINS`.
3. The free API service runs the queue worker **inside** the API process (`RUN_EMBEDDED_WORKER=true`) because Render free has no background workers and uploads live on ephemeral disk. Files are deleted after processing anyway.
4. Add reference frames to `data/reference/` and commit `data/reference/index.json` (built with `tools/index_reference.py`) if you want movie/series scene matching; anime works without it.
5. After changing `NEXT_PUBLIC_API_URL`, redeploy the web service (it is baked in at build time).

## 4. UptimeRobot (keep awake)
Render free services sleep after ~15 min idle. In UptimeRobot add a monitor (HTTP(s), 5-minute interval) for `https://<api>.onrender.com/ping` and optionally `https://<web>.onrender.com/`. `/ping` accepts HEAD (UptimeRobot's free default) and never touches the database, so Neon can still suspend. The UI shows a "waking the free server" banner if a cold start takes >3 s.

## Local
See README. `RUN_EMBEDDED_WORKER=false` + `python -m worker.main` locally, or set it to `true` and skip the second terminal.
