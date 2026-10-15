# Verification notes for the SceneSeek archive

Checks run while preparing this ZIP:

- `python -m compileall -q apps/api/app apps/worker/worker tools` — passed.
- `PYTHONPATH=apps/api:apps/worker pytest -q` — **11 passed**.
- Synthetic 4-frame reference index built with `tools/index_reference.py`; recognition of an exact known frame returned the expected synthetic title at score 1.0 — passed. This synthetic test validates wiring only and is not a real-world accuracy metric.
- JSON and YAML configuration parsing — passed.
- TypeScript transpilation of all four TSX app files — syntax passed.

Not completed in this environment:

- `npm install`, Next.js type-check/lint/build — package download timed out before dependencies were installed.
- Docker image build / compose run — no Docker runtime was available.
- Real-media evaluation, provider free-tier verification, live deployment, restore/backup drill, privacy/rights review, and independent security review.

The GitHub Actions workflow is configured to run backend tests, Python dependency auditing, frontend install/audit/type-check/lint/build on a network-enabled runner. Run those checks and fill `tests/fixtures/labels.json` before making performance claims.
