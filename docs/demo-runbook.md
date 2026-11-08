# Demo runbook

_Owner: S2 (handed over by A4). One page._

## Before going on stage
1. Build the data once (next section), then `make demo` builds the frontend and starts **one process** on :8000.
   Demo mode is on by default. Add `EXPOSURE_SOURCE=eps` for real data. Add `RELAY_PLAINTEXT=1` **only** if the
   H38 encryption go/no-go failed (then drop the encryption claim).
2. Open `http://localhost:8000`, and the family view on a second screen or phone (see `real-phone.md`).
3. `curl -X POST localhost:8000/api/demo/reset` for a clean slate.
4. `make smoke` in a second terminal: every line should be PASS, including `closure -> reroute`.

## Building the whole city with EPS reports
`data/` is gitignored, so every machine builds its own. From `backend/`, with the venv active:

1. `python -m scripts.data.fetch_eps` pulls the last year of EPS occurrences into `data/raw/eps/eps_occurrences.geojson`.
2. Download the Alberta extract (about 340 MB) from Geofabrik into `data/raw/osm/`:
   `https://download.geofabrik.de/north-america/canada/alberta-latest.osm.pbf`
3. `python -m scripts.routing.build_graph --osm-file ../data/raw/osm/alberta-latest.osm.pbf` (about 5 min).
   Without `--osm-file` it asks Overpass, which often refuses a request this big.
4. `python -m scripts.data.build_exposure --source eps --radii 100` (about 5 min).
5. Start the backend with `EXPOSURE_SOURCE=eps`.

The graph holds walking and driving on the same edges (Walk / Drive on the Plan page). Driving uses one-way streets
and posted speeds (free-flow, no traffic). A graph built before driving existed still loads, as walking only.

Walking and driving score reports differently. Driving uses the exposure build (step 4: last 7 days, each report
shared among nearby streets). Walking uses `waykin/data/walk_pressure.py`, built at server startup in about a second:
the last 30 days (what the map shows), weighted by how close the route passes, how recent (14-day half-life) and how
serious each report is. Severity runs 1 to 5 (`severity` in `waykin/data/categories.yaml`, homicide 5, indecent act
1.5, theft 1); the map shades each dot from light to dark red by its most serious report, using the same weights.
Driving's catchment radii use the separate `catchment` table. Each trip offers two routes: fastest, and lower-exposure
(the route with the fewest weighted reports that is at most 40% slower, `MAX_EXTRA_TIME` in `constants.py`). The Plan
page starts on the lowest-pressure walking route when WayKin abstains.

No-go zones: every spot whose most serious report in the last 30 days is a homicide or weapons offence (severity 3.5
or more, the dark end of the dot colours) gets a 100 m circle. In both modes the lower-exposure route first keeps as
much of its length out of these circles as the time cap allows, then minimises reports passed, and WayKin recommends
it whenever it spends less time in them than the fastest route. Tune with `AVOID_MIN_SEVERITY`, `AVOID_RADIUS_M` and
`AVOID_MINUTES_PER_M` in `constants.py`. The map key (top right) is a vertical scale
from the most serious category (top, dark red) to the least serious (bottom, light red).

A new graph invalidates every exposure build, so after step 3 always redo step 4. Routes count the last 7 days of
reports (the map still shows up to 30 days); an exposure built before this change needs step 4 again.

## Demo account
In demo mode (the default) the server creates (at startup, if missing) the account `demo`, password `waykin-demo`
(override with `DEMO_PASSWORD`), and a "Demo family" with Maya, Sam and Priya at fixed, made-up spots
(`backend/waykin/demo/people.json`). Sign in as `demo` and they appear as pins on the Plan map; tap one and choose
Start here or End here. No other account ever gets those spots. The demo account can't delete itself or remove
family members, since everyone trying the published demo shares it. A restart re-adds anything missing.

## Presets
Real-mode presets live in `backend/waykin/demo/presets.json` (empty until H24, when real routes work).
Each entry is a `DemoPreset` plus, for the `reroute` preset, a `hazard` the API never exposes:

```json
{"id": "reroute", "name": "Closure on the way", "description": "...",
 "origin": {"lat": 0, "lon": 0}, "destination": {"lat": 0, "lon": 0}, "expected": "reroute",
 "hazard": {"lat": 0, "lon": 0, "radius_m": 40, "description": "Closure: utility works on the sidewalk"}}
```

Pick the hazard point on the planned fastest route (A3 can supply it). `make smoke` checks the closure
really lands on the route and that the reroute avoids it.

| # | Expected | What to show |
| --- | --- | --- |
| 1 | `recommend` | Fastest vs lower-exposure, "holds in N of 500 simulations", provenance banner |
| 2 | `abstain` | The abstain card: the data can't tell the routes apart, so we don't pretend |
| 3 | `reroute` | Start walking, share the link, trigger the closure → client reroutes, family view updates |

## Commands
- Trigger the scripted closure: `curl -X POST localhost:8000/api/demo/trigger/<preset id>` (replaces any earlier demo closure).
- Reset between runs: `curl -X POST localhost:8000/api/demo/reset` (clears hazards, ends journeys, closes relay sockets).
- Both return 404 unless `DEMO_MODE=1`.

## If something breaks
- Blank map: check the terminal for a startup error (missing `data/build/`?) and run `make build-data`.
- Family view stuck on "reconnecting": reload it; the share link carries everything it needs.
- Worst case: `make mock-demo` serves fixtures with a working relay and the `mock-reroute` preset.
