.PHONY: api worker web test index
api:
	uvicorn app.main:app --app-dir apps/api --reload --host 127.0.0.1 --port 8000
worker:
	PYTHONPATH=apps/api:apps/worker python -m worker.main
web:
	cd apps/web && npm run dev
test:
	PYTHONPATH=apps/api:apps/worker pytest -q
index:
	python tools/index_reference.py --algorithm dhash
