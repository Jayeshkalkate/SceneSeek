# Architecture and data flow

```text
Browser / Next.js
      │ multipart upload (HTTPS in deployment)
      ▼
FastAPI ── validates extension/MIME/size/image bytes ──> private storage
      │
      └── creates a persistent job ──> SQLAlchemy DB queue
                                      │ claim with FOR UPDATE SKIP LOCKED on PostgreSQL
                                      ▼
                           Independent worker process
                           ├─ download temporary upload
                           ├─ FFprobe validation for video
                           ├─ sample ≤12 frames via FFmpeg
                           ├─ perceptual-hash dedupe
                           ├─ dHash or CLIP image representation
                           ├─ optional OCR / ASR signals
                           ├─ visual + text signal fusion
                           └─ rank ≤5 candidates, margin/confidence gate
                                      │
                                      ▼
                        job result in DB / browser polling
```

## Process boundaries

- The API is responsible for validation, upload handling, rate limiting, job creation, polling, feedback and status reads. It does not load a heavy vision model.
- The worker is responsible for FFmpeg, optional CPU-bound models and recognition. It can be restarted independently and retries transient processing errors with a bounded attempt count.
- SQLite is convenient for one-machine development. For independent API and worker instances, configure PostgreSQL and a private shared object bucket; SQLite files and local upload directories must not be assumed to be shared across unrelated hosts.
- `data/reference/index.json` is a read-only deployment artifact containing title metadata plus dHash values or CLIP embeddings. In PostgreSQL mode, the same builder can also populate `titles` and `ref_frames` in pgvector.

## Recognition and confidence

A title score is a **ranking score**, not a calibrated probability. The default fusion uses visual similarity heavily, then adds OCR text and ASR transcript evidence only when available. The highest candidate is labeled high only when both its score and its margin over the runner-up clear configured starter thresholds. A low margin deliberately produces an ambiguous result. Thresholds should be calibrated on a held-out labeled set before describing any band as reliable.

The dHash path mainly identifies near-identical frames and is a development baseline. CLIP usually retrieves semantically similar scenes more effectively but can confuse visually similar titles, characters, lighting or studio styles. Neither method can recognize titles that are absent from the reference collection.

## Data lifecycle

- Uploads are randomly named and stored privately. A successfully processed or terminally failed upload is deleted immediately; the worker also removes stale local upload files on its periodic cleanup cycle.
- For Supabase Storage, set a server-side lifecycle/cleanup policy for the private `uploads` bucket as a second line of defense. The database purge function only nulls stale paths; it does not replace bucket retention policy.
- Feedback and takedown requests contain only the submitted fields. Keep user-provided feedback notes short, and publish a privacy/rights-contact policy before a public launch.

## Graceful degradation

- No index: return a clear no-match/setup message rather than a fabricated title.
- Invalid or overlong video: fail before model inference and give an actionable reason.
- Missing OCR/ASR extras: visual recognition still runs; those signals are simply omitted.
- Missing public metadata: the candidate remains usable with fields marked unavailable. Metadata endpoints must not block the recognition result.
- No evaluation report: the dashboard explicitly says accuracy has not yet been measured.
