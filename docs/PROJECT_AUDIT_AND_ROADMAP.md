# SceneSeek project audit and improvement roadmap

This checklist distinguishes implemented foundations from items that still need runtime or real-data verification. Passing unit tests does not prove live deployment correctness or recognition accuracy.

## Fixes applied in this archive

- Private job status/results now require the owning signed-in user when `jobs.user_id` is set. Missing and non-owner access both return 404 to avoid disclosing whether a private job exists.
- Feedback submission applies the same owner check for private jobs.
- The API root redirects browsers to `FRONTEND_URL` when configured, avoiding the confusing JSON-only landing page on the API's public URL. Without that setting, it returns a clear API service descriptor. API docs remain at `/docs`.
- Render Blueprint sets `FRONTEND_URL` to the default Render URL for `sceneseek-web`. If you rename the service or configure a custom domain, update this value.
- Frontend metadata now declares the supplied SceneSeek logo as the site icon.
- Integration tests cover private-job authorization and API-root redirect behavior.

## Must verify before public launch

1. **Render services:** Deploy both `sceneseek-api` and `sceneseek-web` from `render.yaml`. Open the URL for the web service to see the site. API URL is for API calls and `/docs`.
2. **Environment variables:** Set API `DATABASE_URL`, `CORS_ORIGINS`, and `FRONTEND_URL`; set web `NEXT_PUBLIC_API_URL`. Rebuild the web service after changing `NEXT_PUBLIC_API_URL` because it is embedded during Next.js build.
3. **Database migrations:** Check the SQLAlchemy models against `supabase/migrations/0001_init.sql` and any existing hosted database. Back up before applying schema changes.
4. **Storage:** Use private object storage for multi-instance deployments. Local container files can be ephemeral and may not be visible to a separate worker.
5. **Anonymous jobs:** Anonymous jobs remain accessible by their high-entropy job UUID so the anonymous upload/poll workflow works. For stronger privacy, add a separate per-job secret token returned once on upload and required for every anonymous poll/feedback request.
6. **Rate limits:** Current in-process limits are not shared across replicas. Use a gateway or shared rate-limit store before scaling or exposing uploads broadly.
7. **AI accuracy:** Movie/series recognition is closed-set and needs a lawful reference index. Build a labeled held-out test set and report Top-1, Top-5, MRR, high-confidence precision, false-match rate and latency. Do not treat score bands as calibrated probabilities unless calibrated.
8. **Provider failures:** Test timeouts, provider rate limits, empty metadata, invalid image URLs and offline operation. Provide a useful no-match result instead of fabricating a title.
9. **Privacy/legal:** Publish accurate privacy, retention, terms and rights-holder removal information. Ensure these policies reflect the actual providers and data flows used.
10. **Operational checks:** Verify backups/restores, job retries, worker restart recovery, stuck-job cleanup, upload TTL cleanup, logging without secrets, monitoring and dependency audits.

## Suggested page roadmap

### P0 — before public launch
- Search/result experience with loading, failed, ambiguous and no-match states.
- Privacy and terms pages that reflect actual data processing and retention.
- Help page with accepted formats, size limits, troubleshooting and recognition limitations.
- Secure job ownership checks and abuse protection.

### P1 — reliability and trust
- Results correction/reporting workflow with moderation queue.
- History deletion and account/data deletion flows.
- Admin-only operations view for queue depth, failed jobs and provider health; protect it with server-side role checks.
- Accessible keyboard navigation, reduced-motion support and clear upload progress.

### P2 — differentiated features
- Personal watchlist and saved discoveries.
- More robust candidate ranking with visual, OCR and optional audio signals.
- Multilingual OCR and query filters.
- Model comparison dashboard driven by a reproducible labeled evaluation set.

## Local verification commands

```bash
PYTHONPATH=apps/api:apps/worker pytest -q
python -m compileall -q apps/api/app apps/worker/worker tools
cd apps/web && npm ci && npm run typecheck && npm run lint && npm run build
```

The web commands require a valid npm lockfile. If the repository does not include `package-lock.json`, run `npm install` once, review and commit the generated lockfile, then use `npm ci` for reproducible builds.
