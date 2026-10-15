# SceneSeek

**See it. Seek it. Find it.** — Identify movies, series, and anime from a screenshot or a short video clip.

SceneSeek is a free-tier-first BTech project: Next.js frontend, FastAPI API, a separate worker, a persistent job queue, a reference-frame indexing tool, deterministic ranking with an uncertainty gate, feedback, evaluation metrics, and deployment templates. It has no required paid service, no required API key for local development, no social-media scraping, and no bundled copyrighted reference clips.

> **Important:** SceneSeek is a closed-set visual search system. It can only identify titles represented in the reference index. Do not claim broad/production accuracy until you have built a lawfully sourced index and evaluated it on labeled held-out clips. A cleanly running app is not evidence that the AI has been validated.

## What's new in this version

- **Anime now works out of the box, no index needed.** Screenshots/clips are matched through the free [trace.moe](https://trace.moe) API, with metadata from AniList (title, episode, timestamp, poster). Controlled by `ENABLE_ONLINE_ANIME` (default `true`; set `false` to stay fully local). Note: with this on, anime frames are sent to trace.moe. Adult-flagged results are dropped.
- **Title search by name** (`GET /v1/search?q=`, plus a search box on the homepage) for movies (Apple iTunes Search, no key), series (TVmaze), anime (AniList) and OMDb if you set a key.
- **Fixed:** dHash scoring no longer returns junk low-confidence candidates for unrelated images.
- **Fixed:** frontend dependency/ESLint config (version ranges, native flat ESLint config for Next 16) and read rate limit (polling could hit 429).
- Movies/series *scene recognition* still requires your own lawful reference index (below). No free public API does screenshot-to-movie matching.

## What is implemented

- Responsive dark/neon SceneSeek UI using the supplied logo.
- Screenshot upload (`jpg`, `png`, `webp`, up to 10 MB) and video upload (`mp4`, `webm`, `mov`, up to 25 MB / 30 seconds).
- Server-side MIME/content validation, size limits, generated file names, FFprobe validation, frame sampling, perceptual-hash deduplication, and transient upload cleanup.
- Persistent job queue (`queued → processing → done/failed`); the worker can run independently of the API.
- Visual search against an index built from your own legally sourced reference frames. Exact/near-exact dHash matching works with standard dependencies; optional CLIP embeddings are supported for semantic visual similarity.
- Up to five candidates, score/margin-based confidence bands, an explicit no-match state, and signal/evidence fields.
- Feedback endpoint, title details endpoint, health endpoint, evaluation dashboard endpoint, and takedown request endpoint.
- Public-metadata provider adapter scaffolding for AniList/Jikan/TVmaze, with OMDb optional if you provide its free API key. External metadata never substitutes for visual matching.
- Unit tests, evaluation script, SQL migration, Docker Compose, CI, env templates, and deployment/legal notes.

## Fastest local setup (free)

Requirements: Python 3.11+, Node.js 20.9+ (Node.js 22 recommended), npm, and FFmpeg (for video uploads). No paid account or API key is required for local mode. Docker is optional.

### 1. Start the API

From the repository root:

```bash
python -m venv .venv
# Windows: .venv\\Scripts\\activate
source .venv/bin/activate
pip install -r apps/api/requirements.txt
cp .env.example .env
uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000
```

On PowerShell, copy `.env.example` to `.env` and activate with `.venv\\Scripts\\Activate.ps1`.

### 2. Start the worker in a second terminal

Activate the same virtual environment, from the repository root:

```bash
PYTHONPATH=apps/api:apps/worker python -m worker.main
```

Windows PowerShell:

```powershell
$env:PYTHONPATH = "apps/api;apps/worker"
python -m worker.main
```

### 3. Start the frontend in a third terminal

```bash
cd apps/web
npm install
npm run dev
```

Open <http://localhost:3000>. The API docs are at <http://127.0.0.1:8000/docs>.

## Docker Compose

```bash
cp .env.example .env
docker compose up --build
```

Then open <http://localhost:3000>. The API and worker share local runtime storage in Compose. For a cloud Compose deployment, set `DATABASE_URL_DOCKER` to PostgreSQL and configure shared object storage (such as a private Supabase Storage bucket); do not rely on a local SQLite file across independent containers. The `.env.example` database value is intended for non-Docker local development.

## Build the reference index (required for useful identification)

The repository intentionally does not ship a collection of copyrighted film frames. Add reference material you have the right to process under `data/reference/<title-slug>/frames/` and a `metadata.json` next to `frames/`.

Example:

```text
data/reference/
  nosferatu/
    metadata.json
    frames/
      0001.jpg
      0002.jpg
```

`metadata.json` example:

```json
{
  "title": "Nosferatu",
  "original_title": "Nosferatu, eine Symphonie des Grauens",
  "kind": "movie",
  "year": 1922,
  "synopsis": "A public-domain silent horror film.",
  "genres": ["Horror"],
  "poster_url": null,
  "rating": {"value": null, "source": null},
  "external_url": "https://archive.org/",
  "provider": "manual",
  "attribution": "Add the exact source and license for each frame here."
}
```

Build a lightweight dHash index (works without downloading an AI model):

```bash
python tools/index_reference.py --algorithm dhash
```

For CLIP embeddings, install the optional worker extra and run the same tool with `--algorithm clip`:

```bash
pip install -r apps/worker/requirements-clip.txt
python tools/index_reference.py --algorithm clip
```

**The index and upload processing must use the same algorithm.** A dHash index is suitable mainly for duplicates/near-duplicates; CLIP is better for semantic visual similarity but is still not an exact scene recognizer. Keep the index source/license/attribution documented. Don't scrape social platforms or use material you don't have rights to use.

## Run tests and evaluation

```bash
pip install -r apps/api/requirements-dev.txt
PYTHONPATH=apps/api:apps/worker pytest -q
```

After you prepare a labeled test set, add entries to `tests/fixtures/labels.json` and run:

```bash
python tools/evaluate.py --labels tests/fixtures/labels.json --output reports/evaluation.json
```

The evaluator reports Top-1, Top-5, MRR, and per-confidence-band accuracy. A small or biased test set can produce misleading numbers; keep evaluation clips separate from reference frames where possible. Confidence thresholds are starting values, not a calibration guarantee.

## Environment and security notes

- `.env` is never committed. Keep `SUPABASE_SERVICE_KEY`, `OMDB_API_KEY`, and `WORKER_SHARED_SECRET` server-side only.
- `CORS_ORIGINS` must be a comma-separated allowlist in production; do not use `*` with credentials.
- The API applies IP-based in-process rate limits. Use a shared gateway/rate limiter if running multiple API replicas; process-local limits do not aggregate across replicas.
- The optional worker shared-secret protects worker-only control routes if you add them; this project does not expose an unauthenticated admin endpoint.
- Upload files are private, randomly named, and automatically removed after processing or by TTL cleanup. Set storage lifecycle policies too when using remote storage.
- The API is designed for public uploads but is **not a substitute for a professional security audit**. Before a public launch, add abuse monitoring, CDN/WAF limits, backups, dependency scanning, privacy notice, rights-holder contact details, and verify current free-tier quotas.

## Free-tier deployment outline

- **Frontend:** Vercel Hobby (or any free static/frontend host).
- **API and worker:** two Docker-based free CPU Spaces/containers, or one small service for a demo.
- **Database/object storage:** Supabase Free (Postgres + a private `uploads` bucket). Configure `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, and `SUPABASE_BUCKET` as server-side secrets.
- **CI:** GitHub Actions on a public repository.

Free tiers and provider policies change. Read `docs/deployment.md` and re-check the provider terms/quotas before deploying. The app remains free to run locally even if a host later changes its terms.

## Repository map

- `apps/web` — Next.js website.
- `apps/api` — FastAPI endpoints, schemas, persistence, validation, rate limit, and storage.
- `apps/worker` — independent queue worker and video/recognition pipeline.
- `tools/index_reference.py` — idempotent reference index builder.
- `tools/evaluate.py` — closed-set evaluation.
- `supabase/migrations` — PostgreSQL schema migration.
- `tests` — unit and API smoke tests.
- `docs` — architecture, deployment, legal/ethical data handling.

## License

Application source code is released under the MIT License. This does not change the licenses or rights attached to any reference media, posters, datasets, models, or third-party metadata.

## Validation status for this archive

- Python compile check: passed. Pure-logic unit tests for the new online/merge code passed in a stubbed environment.
- TSX syntax transpilation: passed.
- Not run here (no network in the build sandbox): `pip install`, the full pytest suite, `npm install`/`next build`, Docker builds, and live calls to trace.moe/AniList/TVmaze/iTunes. Run `make test` and `npm run build` after cloning; CI does this on push.
- Closed-set accuracy for movies/series is unmeasured until you build an index and run `tools/evaluate.py`.
