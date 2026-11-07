# Demo runbook

_Owner: S2 (handed over by A4). One page._

## Before going on stage
1. `make build-data` once (graph + synthetic exposure; EPS too if `data/raw/` has the snapshot).
2. `make demo` builds the frontend and starts **one process** on :8000 with `DEMO_MODE=1`.
   Add `EXPOSURE_SOURCE=eps` for real data. Add `RELAY_PLAINTEXT=1` **only** if the H38 encryption go/no-go failed (then drop the encryption claim).
3. Open `http://localhost:8000`, and the family view on a second screen or phone (see `real-phone.md`).
4. `curl -X POST localhost:8000/api/demo/reset` for a clean slate.

## Preset order
| # | Preset | What to show |
| --- | --- | --- |
| 1 | `recommend` — Campus to Old Strathcona | Fastest vs lower-exposure, "holds in N of 500 simulations", provenance banner |
| 2 | `abstain` — Short hop near campus | The abstain card: the data can't tell the routes apart, so we don't pretend |
| 3 | `reroute` — Closure on the way | Start walking (simulated), share the link, then trigger the closure → client reroutes, family view updates |

## Keys and commands
- **`h`** (presenter key) triggers the scripted closure for the active preset. Same as `curl -X POST localhost:8000/api/demo/trigger/reroute`.
- Reset between runs: `curl -X POST localhost:8000/api/demo/reset` (clears hazards, journeys, relay sockets).
- Runs are deterministic: same preset → same routes and numbers (fixed seeds, fixed `as_of`).

## If something breaks
- Blank map: check the terminal for a startup error (missing `data/build/`?) and run `make build-data`.
- Family view stuck on "reconnecting": reload it; the share link carries everything it needs.
- Worst case: `WAYKIN_MOCK=1 DEMO_MODE=1` serves fixtures with a working relay.
