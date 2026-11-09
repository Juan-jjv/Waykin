### ⚠️ DISCLAIMER: COMMIT HISTORY DOES NOT REFLECT WHO DID THE WORK

**OUR WHOLE TEAM CODED TOGETHER IN ONE VS CODE LIVE SHARE SESSION. BECAUSE OF THAT, ONLY ONE PERSON (THE SESSION HOST) MADE GIT COMMITS. THE COMMIT HISTORY AND GITHUB CONTRIBUTOR STATS ARE NOT REFLECTIVE OF THE WORK EACH TEAMMATE DID.** EVERY TEAMMATE WROTE CODE FOR THIS PROJECT. 

# WayKin

**Walking and driving routes around Edmonton that are honest about what the crime data can and can't tell you.**

Built during the 64-hour natHacks 2026 hackathon.

## Links

| What | Link |
| --- | --- |
| Slides | [Canva presentation](https://canva.link/jed3kdylaoxf2r7) |
| Project write-up | [Google Doc](https://docs.google.com/document/d/1yqoS5TwJQ5T2rmIlGyvLvRPLxJCT4Yt_-RFzJuo5Edw/edit?tab=t.0) |
| Project summary | [Google Doc](https://docs.google.com/document/d/124v9pcVoVGEwVv9_4piwC2cBHF3PFz6c4nzHSTD7Vck/edit?tab=t.0) |
| Source code | This repository |

To try the app, run it locally with the steps in [Run it](#run-it). It takes about 10 minutes, and all the data is included.

## What it does

People travelling alone, especially at night, often want a route that avoids streets with many reported incidents, and their families want to know they got home. Most tools either ignore that data or turn it into a "safety score" that claims more than police reports can tell you. WayKin tries to be honest instead.

- **Two routes to compare.** For a start and a destination, WayKin shows the fastest route and, where one exists, a lower-exposure route, for walking or driving.
- **Real numbers, not ratings.** Each route shows the reported incidents near it, with a likely range and the street segments that contribute most.
- **It only recommends a route when the difference is real.** A route is recommended only if it has at least 15% fewer reported incidents than the fastest route in at least 90% of 500 simulations, while adding no more than 40% to the travel time. Otherwise WayKin says why it won't pick one: too little data, routes too close to call, a detour that costs too much time, or no real alternative.
- **Incident map.** Edmonton Police Service reports from the last 30 days, filterable by category and date, plus police stations you can route to.
- **Family sharing.** Family groups, and live location sharing that is end-to-end encrypted: the server only passes along data it can't read.
- **Live rerouting.** If a closure appears on your route mid-walk, your app finds a way around it, and the family view updates.
- **Voice message (prototype).** A microphone button under the map records a short message. In this version the recording is thrown away, not stored or sent.

## How it works

1. **Street network.** The OpenStreetMap walking and driving network for Edmonton is built offline into a compact graph.
2. **Spreading the reports.** EPS publishes reports at intersections, not exact addresses. Each intersection's reports are shared out among the nearby street segments.
3. **Handling uncertainty.** 500 random simulations of where reports really were, and of how much small counts can be trusted, give a range for every street segment, not a single number.
4. **Routing.** Dijkstra's algorithm runs 12 times with different trade-offs between time and incidents, and the fastest and best lower-exposure routes are kept. Each request takes milliseconds.
5. **Recommending or not.** Every candidate route is scored in all 500 simulations at once, and the recommendation rule above runs on those results.
6. **Realtime.** Journeys, the encrypted location relay and closure alerts run over WebSockets in the same server.

## Run it

You need Python 3.11+ and Node 20+.

1. Clone it (over 1 GB, since the Edmonton data is included):
   ```bash
   git clone https://github.com/Juan-jjv/Waykin.git
   cd Waykin
   ```

2. Install:
   ```bash
   python -m venv backend/.venv
   backend\.venv\Scripts\activate        # Windows
   source backend/.venv/bin/activate     # Mac/Linux
   pip install -e "backend[dev,build]"
   cd frontend
   npm ci
   npm run build
   cd ..
   ```

3. Unpack the data and turn on the real incident reports:
   ```bash
   cd backend
   python -m scripts.data.snapshot restore
   python -c "open('.env', 'w').write('EXPOSURE_SOURCE=eps')"
   ```

4. Start it:
   ```bash
   uvicorn waykin.main:app --port 8000
   ```

5. Open http://localhost:8000 and sign in as `demo`, password `waykin-demo`.

Next time, just activate the venv (step 2), `cd backend`, and do step 4.

### Trying the demo

The plan screen has three **Demo walks** you can pick with one tap:

1. **Worth the detour:** WayKin recommends a slightly longer route with noticeably fewer reported incidents.
2. **Too close to call:** the routes are about the same, so WayKin doesn't pick one.
3. **A clear winner:** one route has far fewer reported incidents, so WayKin recommends it with confidence. To see live rerouting, start this walk, then close a street on the route with `curl -X POST http://localhost:8000/api/demo/trigger/reroute`.

To see family sharing, start a walk and open the share link in a second browser window.

### On a phone

Phones only give location to HTTPS sites. To test on a real phone, expose your local server through a free HTTPS tunnel such as [Cloudflare quick tunnels](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/): `cloudflared tunnel --url http://localhost:8000`. See [docs/real-phone.md](docs/real-phone.md).

## Requirements

**Software**

| Layer | Tools |
| --- | --- |
| Backend | Python 3.11+, FastAPI, Pydantic, uvicorn |
| Routing and data | NumPy, SciPy (sparse graph routing), pandas, PyArrow, Shapely, pyproj; OSMnx for the offline graph build |
| Frontend | Node 20+, React 18, TypeScript, Vite, MapLibre GL, TanStack Query, React Router |
| Realtime | WebSockets, WebCrypto (AES-GCM) |
| Testing | pytest, Vitest, ESLint, ruff |

The full lists are in [backend/pyproject.toml](backend/pyproject.toml) and [frontend/package.json](frontend/package.json). Everything runs as one server process, with SQLite for accounts and no other database.

**Hardware**

- Any laptop or desktop running Windows, macOS or Linux. No special hardware is needed.
- About 3 GB of free disk space (repository, unpacked data and dependencies) and 8 GB of RAM recommended.
- Optional: a phone with GPS, to try live walks and family sharing on a real device.

## Tests

```bash
cd backend && pytest -q -m "not timing"
cd frontend && npm test && npm run lint:words
```

`lint:words` blocks words such as "safe" and "dangerous" from the app's text, because the data can't support those claims.

## Data, privacy and limitations

> Counts of reported incidents near street segments, from public police data. They describe the past, not what will happen on your walk. Not for comparing neighbourhoods.

- Every route response states its data source, the as-of date and the disclaimer above.
- Only intersection-level points, as EPS publishes them, are used. WayKin never derives addresses and makes no comparisons between neighbourhoods.
- Live location sharing is encrypted in the browser. The key is in the share link's `#fragment`, which browsers never send to the server. Anyone who has the link can follow the walk.
- WayKin often declines to recommend a route. That's on purpose: the honest answer is often "it doesn't matter".
- The full threat model is in [docs/threat-model.md](docs/threat-model.md).

## Sources and credits

**Data**

- [Edmonton Police Service](https://www.edmontonpolice.ca/), for the incident report data (snapshot as of Nov 6, 2026).
- [OpenStreetMap](https://www.openstreetmap.org/copyright) contributors, for the street network and map data (© OpenStreetMap contributors, ODbL).
- [City of Edmonton Open Data](https://data.edmonton.ca/), for traffic disruptions and closures.
- [Statistics Canada](https://www.statcan.gc.ca/), for the police-reported crime trends cited in our write-up.

**Team WayKin**

- Japan Patel
- Juan Joseph Vijay
- Badal Patel
- Jay Patel

All code was written during natHacks 2026. AI coding assistants (Claude and Cursor) were used during development and are credited as co-authors on the commits where they were used.

**Thanks** to the natHacks 2026 organizers and mentors.
