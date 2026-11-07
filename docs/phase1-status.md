# Phase 1 status (Gate G1)

Phase 1 = skeleton and mocks: every piece runs end to end on fake data, so nobody waits in Phase 2.

## Gate G1 checklist

| Check | Status |
| --- | --- |
| `make mock` starts; the map shows a mock route with the provenance banner | Done (checked in headless Chrome) |
| Generated TypeScript types match `schemas.py` | Done (`frontend/src/api/types.gen.ts`; CI `contract` job) |
| CI is green: ruff, pytest, typecheck, eslint, vitest, lint:words, no-data | Done locally (44 backend + 14 frontend tests) |
| Smoke test passes | Done: 14 pass in `make mock-demo`, including closure→reroute |
| `data/build/graph/` exists for the real demo area | **To do on the host:** `make build-data` needs network for OpenStreetMap |

## What is real now vs. stubbed

| Area | Real now | Stubbed until |
| --- | --- | --- |
| A4 | pyproject, constants (spec v2), schemas (B5 + WebSocket models), config, mock mode with fixtures, journeys, relay (plaintext **and** e2ee envelope checks, all close codes), hazard store + public stream, security headers, log hygiene, SPA serving, Makefile, CI | Real-mode preset coordinates in `demo/presets.json` (H24, needs real routing). **Done since G1:** `/api/demo/trigger` + `/api/demo/reset`, `mock-reroute` preset, privacy suite (`tests/privacy`), full-flow test (`tests/api/test_demo_full_flow.py`) |
| A3 | `types.py`, `Graph`, snapping, artifacts read/write, `make_grid_graph`, OSM `build_graph.py` (untested here: no network) | `shortest_path`, `candidate_set` (H15), real `service.plan` (H18; stub returns a straight line), `hazard_edges` (H29) |
| A2 | `simulate` with the v2 prior, `assess` and `_decide` (all four abstain reasons + radius sensitivity), `make_synthetic_bundle_for_tests`, `validate_source_table` | `SyntheticSource.load` (H13), `EpsSource` (H14), `build_allocation` (H16), `build_exposure` + `load_exposure` (H21) |
| A1 | App shell, 3 routes, MapView + ProvenanceBanner, PointPicker, RouteLayer with top segments, RoutePanel with abstain cards, `src/geo` (RealGeo, SimGeo), lint-words | Incident layer, filters, radius select (H19), walker and family screens (H22–H26) |
| A4 lib | `crypto.ts` (real AES-GCM), `relay.ts` (walker + viewer, reconnect, seq), `buildShareLink` | Wiring into the walker and family screens (A1, Phase 3) |
| S1 | `smoke/smoke.py` | Grows with each phase; Phase 3 checks already written |

## First commands on the host laptop

```bash
make install          # once
make mock             # open http://localhost:5173, click two points, Find routes
make smoke            # in a second terminal, while a server runs
make build-data       # needs internet: builds data/build/graph/ for the real demo area
```

Note: real mode (`make dev` without `WAYKIN_MOCK=1`) cannot start until A2's `load_exposure` lands in Phase 2. That is expected: use `make mock` until then.
