# WayKin (owner: A4). Run everything from the repo root. Only the host's human starts or stops servers.
SHELL := /bin/bash
export DATA_DIR ?= $(CURDIR)/data
UVICORN := uvicorn waykin.main:app --workers 1 --no-access-log --port 8000

.PHONY: install dev api web mock build-data restore-data pack-data test gen-types demo mock-demo smoke tunnel

install:            ## once, on the host laptop
	pip install -e "backend[dev,build]"
	cd frontend && npm ci

dev:                ## backend :8000 + Vite :5173 (Vite proxies /api, including WebSockets)
	$(MAKE) -j2 api web

api:
	cd backend && $(UVICORN) --reload

web:
	cd frontend && npm run dev

mock:               ## same as dev, but every endpoint serves fixtures; no data needed
	WAYKIN_MOCK=1 $(MAKE) dev

build-data:         ## graph (needs network for OSM), then exposure (Phase 2: build_exposure)
	cd backend && python -m scripts.routing.build_graph
	@if [ -f backend/scripts/data/build_exposure.py ]; then \
	  cd backend && python -m scripts.data.build_exposure --source synthetic && \
	  if [ -d "$(DATA_DIR)/raw/eps" ]; then python -m scripts.data.build_exposure --source eps; else echo "no EPS snapshot: skipping eps"; fi; \
	else echo "build_exposure.py not written yet (Phase 2, A2)"; fi

restore-data:       ## unpack the committed snapshot in data-split/ into data/ (checks the parts first)
	cd backend && python -m scripts.data.snapshot restore

pack-data:          ## after rebuilding data/, repack it into data-split/ (49 MB parts) to commit
	cd backend && python -m scripts.data.snapshot pack

test:
	cd backend && pytest -q -m "not timing"
	cd frontend && npm test && npm run lint:words

gen-types:          ## regenerate frontend/src/api/types.gen.ts from the mock server's OpenAPI
	cd backend && (WAYKIN_MOCK=1 $(UVICORN) & echo $$! > /tmp/waykin-gen.pid) && sleep 3
	cd frontend && npm run gen:types; status=$$?; kill $$(cat /tmp/waykin-gen.pid); exit $$status

demo:               ## one process on :8000 serving the built frontend, real data, demo presets
	cd frontend && npm run build
	cd backend && DEMO_MODE=1 $(UVICORN)

mock-demo:          ## like demo, but on fixtures (works before Phase 2 lands)
	cd frontend && npm run build
	cd backend && WAYKIN_MOCK=1 DEMO_MODE=1 $(UVICORN)

smoke:              ## S1's smoke test against a running server (BASE=http://localhost:8000)
	python smoke/smoke.py --base $${BASE:-http://localhost:8000}

tunnel:             ## HTTPS for real-phone GPS. Public URL: refuses EPS data unless ALLOW_PUBLIC_EPS=1.
	@if [ "$${EXPOSURE_SOURCE:-synthetic}" = "eps" ] && [ "$${ALLOW_PUBLIC_EPS:-0}" != "1" ]; then \
	  echo "Refusing: the tunnel makes the app public and EXPOSURE_SOURCE=eps. Only the team lead may set ALLOW_PUBLIC_EPS=1."; exit 1; fi
	cloudflared tunnel --url http://localhost:8000
