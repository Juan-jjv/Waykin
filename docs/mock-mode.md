# Mock mode (for A1)

`make mock` starts the backend with `WAYKIN_MOCK=1` (no graph, no exposure data) and Vite on :5173.

| Endpoint | In mock mode |
| --- | --- |
| `GET /api/meta` | `waykin/mocks/meta.json`, with live `relay_mode`, `demo_mode`, `demo_presets` |
| `GET /api/incidents` | `mocks/incidents.json`, category filter applied for real |
| `POST /api/routes` | picked by **`floor(origin.lat × 10 000)` parity** — even (e.g. `53.5200`) → `routes_recommend.json`; odd (e.g. `53.5201`) → `routes_abstain.json` (`indistinguishable`) |
| `POST /api/routes/reroute` | same rule on `position.lat`; if an active hazard blocks the fixture's fastest route → `routes_rerouted.json` (avoids the closure) |
| Journeys, relay | **real** (in memory), both e2ee and `RELAY_PLAINTEXT=1` |
| `WS /api/hazards/stream` | snapshot, then **15 s after connect** a fixture closure (`hz_mock_closure`, edge 1006) that overlaps both fixtures' fastest routes |
| `POST /api/hazards` | real; edges resolved against the fixture routes. Needs `X-Admin-Token` (printed at startup) unless `DEMO_MODE=1` |

Test the full reroute loop in mock mode: plan from `53.5200,-113.5200` to `53.5200,-113.5000`, start walking, wait 15 s for the closure, call reroute, and you get the detour.
