.PHONY: setup api worker web test migrate index lint
PY ?= python

setup:
	$(PY) -m pip install -r apps/api/requirements-dev.txt
	$(PY) manage.py migrate
	cd apps/web && npm install

migrate:
	$(PY) manage.py migrate

api:            ## API on http://127.0.0.1:8000 (worker is embedded when using SQLite)
	$(PY) manage.py runserver 127.0.0.1:8000

worker:         ## standalone worker (set RUN_EMBEDDED_WORKER=false for the API first)
	$(PY) manage.py runworker

web:
	cd apps/web && npm run dev

test:
	$(PY) -m pytest -q

lint:
	$(PY) -m compileall -q apps/api/app apps/api/core apps/worker/worker tools
	cd apps/web && npm run typecheck && npm run lint

index:
	$(PY) tools/index_reference.py --algorithm dhash
