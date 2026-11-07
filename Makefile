# WayKin. Run from the repo root. Only the host's human runs dev/mock/demo/tunnel (B0.1 rule 10).
SHELL := /bin/bash
PY ?= python
PORT ?= 8000
export DATA_DIR ?= $(CURDIR)/data
UVICORN := $(PY) -m uvicorn waykin.main:app --workers 1 --no-access-log --port $(PORT)

.PHONY: help install dev mock build-data test test-backend test-frontend gen-types demo tunnel

help:
	@echo "install | dev | mock | build-data | test | gen-types | demo | tunnel"

install:
	$(PY) -m pip install -e "backend[dev,build]"
	cd frontend && npm ci

dev:
	@trap 'kill 0' INT TERM EXIT; \
	(cd backend && $(UVICORN) --host 127.0.0.1) & \
	(cd frontend && npm run dev) & \
	wait

mock:
	WAYKIN_MOCK=1 $(MAKE) dev

build-data:
	cd backend && $(PY) -m scripts.routing.build_graph
	cd backend && $(PY) -m scripts.data.build_exposure --source synthetic
	@if [ -d "$(DATA_DIR)/raw" ] && [ -n "$$(ls -A "$(DATA_DIR)/raw" 2>/dev/null)" ]; then \
		cd backend && $(PY) -m scripts.data.build_exposure --source eps; \
	else echo "no EPS snapshot in $(DATA_DIR)/raw: skipping eps"; fi

test: test-backend test-frontend

test-backend:
	cd backend && $(PY) -m pytest

test-frontend:
	cd frontend && npm test

gen-types:
	@set -e; \
	(cd backend && WAYKIN_MOCK=1 ADMIN_TOKEN=gen $(UVICORN) --host 127.0.0.1) & PID=$$!; \
	trap 'kill $$PID 2>/dev/null' EXIT; \
	for i in $$(seq 1 50); do curl -sf http://127.0.0.1:$(PORT)/api/meta >/dev/null && break; sleep 0.2; done; \
	cd frontend && npm run gen:types

demo:
	cd frontend && npm run build
	cd backend && DEMO_MODE=1 $(UVICORN) --host 0.0.0.0

tunnel:
	@trap 'kill 0' INT TERM EXIT; \
	$(MAKE) demo & \
	for i in $$(seq 1 150); do curl -sf http://127.0.0.1:$(PORT)/api/meta >/dev/null && break; sleep 0.4; done; \
	if command -v cloudflared >/dev/null; then cloudflared tunnel --url http://localhost:$(PORT); \
	elif command -v ngrok >/dev/null; then ngrok http $(PORT); \
	else echo "install cloudflared or ngrok"; exit 1; fi
