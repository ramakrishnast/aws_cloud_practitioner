# CloudCert Lab
#   make run      build everything and start the app on http://localhost:8000
#   make dev      backend with reload + Vite dev server on http://localhost:5173
#   make test     run the backend unit tests

PYTHON ?= python3
VENV   := .venv
PY     := $(VENV)/bin/python
PORT   ?= 8000

.PHONY: run dev setup build test import seed seed-demo docker clean check-python

run: setup build
	@echo ""
	@echo "  CloudCert Lab is starting on http://localhost:$(PORT)"
	@echo ""
	$(PY) -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port $(PORT)

dev: setup
	@echo "Backend: http://localhost:$(PORT)   Frontend (hot reload): http://localhost:5173"
	@trap 'kill 0' INT TERM; \
	  $(PY) -m uvicorn app.main:app --app-dir backend --reload --reload-dir backend --port $(PORT) & \
	  (cd frontend && npm run dev) & \
	  wait

setup: check-python .env $(VENV)/.installed frontend/node_modules/.installed

check-python:
	@$(PYTHON) -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || \
	  (echo "Python 3.10+ is required (found: $$($(PYTHON) --version 2>&1))."; \
	   echo "On macOS: brew install python@3.12, then run: make run PYTHON=python3.12"; exit 1)
	@command -v npm >/dev/null || (echo "Node.js 18+ is required. On macOS: brew install node"; exit 1)

.env:
	cp .env.example .env

$(VENV)/.installed: backend/requirements.txt backend/requirements-dev.txt
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip -q
	$(PY) -m pip install -q -r backend/requirements-dev.txt
	@touch $@

frontend/node_modules/.installed: frontend/package.json
	cd frontend && npm install --no-audit --no-fund
	@touch $@

build: frontend/dist/index.html

frontend/dist/index.html: frontend/node_modules/.installed $(shell find frontend/src -type f 2>/dev/null) frontend/index.html frontend/vite.config.js frontend/tailwind.config.js
	cd frontend && npm run build

test: setup
	cd backend && ../$(PY) -m pytest

# Import every CSV in question_bank/ (normally automatic while the app runs)
import: setup
	cd backend && ../$(PY) -m app.cli import

# Generate ~100 original questions per exam with Claude (needs ANTHROPIC_API_KEY in .env)
seed: setup
	cd backend && ../$(PY) -m app.cli seed --per-exam 100

# Try the generator pipeline offline with placeholder [DEMO] questions (reject them afterwards)
seed-demo: setup
	cd backend && ../$(PY) -m app.cli seed --exam clf-c02 --per-exam 8 --dry-run

docker:
	docker compose up --build

clean:
	rm -rf $(VENV) frontend/node_modules frontend/dist
