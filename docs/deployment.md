# Deployment guide (free-tier-first)

Free plan limits and terms change. This document avoids paid-only dependencies, but you should verify each host's current quotas and policies on the day you deploy. A host may require an account even when its starter tier is free.

## Local development

Use the top-level README instructions. Local SQLite and disk storage require no account or keys. Video uploads require FFmpeg/FFprobe. Screenshot processing can be used even without a system FFmpeg installation.

## Supabase (PostgreSQL + private Storage)

1. Create a Supabase project on a plan you have verified is free.
2. Run `supabase/migrations/0001_init.sql` in the SQL editor or through the Supabase CLI.
3. Create a **private** Storage bucket whose name matches `SUPABASE_BUCKET` (default: `uploads`). Do not expose user uploads through a public bucket.
4. Provide `DATABASE_URL` using the direct or supported pooler connection string. Keep database credentials server-side.
5. Set `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `SUPABASE_BUCKET` only in the API and worker's server-side environment. Never prefix these with `NEXT_PUBLIC_`.
6. Set `USE_PGVECTOR=true` only when using PostgreSQL and after applying the migration. Build your CLIP index with `python tools/index_reference.py --algorithm clip --pgvector`; this also fills `titles` and `ref_frames`. Both the worker and API still need the generated `data/reference/index.json` available for title metadata.
7. Set a Storage lifecycle/retention policy to remove old upload objects. The worker deletes completed uploads immediately; retention is the fallback for interrupted deployments.

When using cloud containers, upload bytes are written from the API to the private bucket and the job stores an opaque bucket path. The worker reads the same path using its server-side storage credentials. With Supabase absent, all uploads are stored on local disk instead.

## Frontend host

Deploy `apps/web` as a Next.js app (for example, on a free frontend plan). Set `NEXT_PUBLIC_API_URL` to the public HTTPS URL of the API. This value is public by design and must not contain secrets. Add the frontend origin to the API's `CORS_ORIGINS` list. If the host does not provide an always-on free backend, expect cold starts or request limits and display them to users.

## API and worker containers

- API: build with `apps/api/Dockerfile`, expose port `7860`, and set the server-side environment variables from `.env.example`.
- Worker: build with `apps/worker/Dockerfile`, point it to the same PostgreSQL `DATABASE_URL`, private Storage bucket and index artifact.
- Set a sensible `JOB_LEASE_SECONDS` above expected cold-start/model-load time. Use PostgreSQL when more than one worker can claim jobs.
- Build the worker with `INSTALL_CLIP=true` if you use CLIP embeddings, then build the reference index with that exact model name. Default `dhash` needs no model download.
- OCR/ASR are optional. Enable them only after installing their optional dependencies and system binaries. They may increase CPU/RAM use and cold-start time on free CPU containers.

## Operations before a public release

- Use HTTPS end-to-end.
- Set exact CORS origins and edge request-body limits. Configure the platform's maximum request body and timeout above the application's 25 MB video limit.
- Configure a private database backup routine and test a restore.
- Set external storage retention, monitor upload volume/egress, and document how users can request deletion.
- Use a shared rate limiter/WAF if the API has multiple replicas; the shipped IP rate limiter is in-process.
- Run `pip-audit`, `npm audit`, tests, and a dependency update review in CI. Check provider terms and free-tier limits before deployment.
- Do not use uptime ping workflows to evade a host's sleeping/cold-start policies. Design the UI to explain startup delays gracefully.
