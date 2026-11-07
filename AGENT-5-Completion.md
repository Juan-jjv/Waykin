# WayKin — Agent A5: Completion

> Context file for the AI coding agent that finishes WayKin. Read this whole file before writing code. Then read **Part B (the shared contract)** of any `AGENT-*.md` spec file: its rules still apply unless this file says a human has changed them.

Written Sat Nov 7, about 15:00 (H20). Feature freeze is **H48 (Sun 19:00)**. Submission is **H62 (Mon 09:00)**.

---

## 0. Where the project stands

**Works today (on `main`, commit `4f5709c`):**
- Real EPS data, as of 2026-11-05: 296 published locations and 938 reports in the demo area. It reaches the app through `build_exposure --source eps`.
- Exposure pipeline: allocation, 500-draw simulation, and `assess` (recommend or abstain). All in `backend/waykin/data/`.
- Real routing: a sweep over 12 time-versus-exposure trade-offs, Pareto selection, and explanations, in `backend/waykin/routing/`.
- The plan screen (MapLibre): incident dots, category filter, route cards, abstain card, stability badge.
- Backend: the journeys API, an encrypted relay, a hazard stream, demo endpoints, and a privacy test suite. 123 backend tests pass.

**Not working or not built:** the Walk and Family screens are placeholders, rerouting is broken by a router bug (task 1.1), and there are no accounts, no families and no family alerts. The pitch numbers haven't been measured.

**How to run it (WSL, from the repo root):**
```bash
source .venv/bin/activate          # REQUIRED: without it, the system Python starts and the app shows "Can't reach the WayKin server"
EXPOSURE_SOURCE=eps make dev       # http://localhost:5173
cd backend && pytest -m "not timing"
cd frontend && npx vitest run && npx tsc --noEmit && npm run lint:words
```
Stop the servers before switching git branches. Vite restarts on config changes and can come back up without its `/api` proxy.

---

## 1. Ground rules (do not break these)

1. **Banned words** anywhere under `frontend/src` or `backend/waykin`: "safe", "safer", "safest", "safety", "unsafe", "danger", "dangerous". This includes comments, docstrings and identifiers. Use "lower-exposure", "fewer reported incidents" or "closure" instead. CI fails on them.
2. **No location logging.** Never log, print, persist or put into an error message any coordinate from a request or relay message. This applies to every new feature below.
3. **No EPS data in git.** `data/raw/**` and `data/build/**` stay gitignored.
4. **Describe routes, never areas.** No colour scales, ratings or wording that rank neighbourhoods. Show counts, never percentages for results.
5. **The server must not be able to link a route request to a person.** `POST /api/routes` and `/api/routes/reroute` take no token, cookie or account (spec B5). New login cookies must be path-scoped so they are never sent to `/api/routes` (see 3.1).
6. **Folder ownership:** each task below names its owner's folder. Where a human owner is still active, make the change on a branch and tell them. Contract changes (new endpoints or fields) need the team lead's approval and an entry in `contract-requests/`.
7. **Do not run git push or merge into `main`.** Work on a branch; humans open PRs and S1 reviews them.
8. **Every task needs tests.** "Done" means its acceptance criteria pass, and backend tests, frontend tests, typecheck and the banned-word lint are all green.

### Needs a human decision before you start
Sections 3 and 4 go beyond the original spec, which lists "user accounts" and "push notifications to closed apps" as out of scope and has no database. **Confirm with the team lead** that these are approved. If they aren't, do sections 2 and 5 only.

---

## 2. P0 — fix before anything else (about 2–3 hours total)

### 2.1 Router corrupts the graph after any closure (SERIOUS)
- **Where:** `backend/waykin/routing/router.py` lines 32–33 (A3).
- **Bug:** `sp.csr_matrix((data, graph.csr.indices, graph.csr.indptr))` shares the graph's arrays, then `matrix.eliminate_zeros()` rewrites them in place. After one request with a blocked edge, every later route is wrong until the server restarts. On the real graph, all 40 trips tested after one closure gave different routes from a clean graph.
- **Do:** pass copies (`graph.csr.indices.copy()`, `graph.csr.indptr.copy()`), or drop blocked edges without changing shared arrays.
- **Accept:** a new test in `backend/tests/routing/` blocks an edge, routes, then checks that `graph.csr.indptr` and `indices` are unchanged and that an unblocked route matches the original.

### 2.2 `make build-data` crashes on osmnx 2.x
- **Where:** `backend/waykin/routing/build.py`, `_undirected_largest` (A3).
- **Do:** call `largest_component` before `to_undirected`: `return ox.convert.to_undirected(ox.truncate.largest_component(G, strongly=False))`.
- **Accept:** `make build-data` finishes on a fresh clone.

### 2.3 Balanced threshold is an absolute count, not 5%
- **Where:** `backend/waykin/routing/pareto.py` lines 38 and 52 (A3).
- **Do:** compare against `fastest.exposure_mean * (1 - BALANCED_MIN_REDUCTION)`. First confirm the intent in A3's spec.
- **Accept:** no balanced route is less than 5% lower than fastest. On 200 real trips, 24 of 184 currently are.

### 2.4 Route order breaks the contract
- **Where:** `pareto.py` line 55. B5 says fastest first, then balanced, then lower_exposure.
- **Do:** order the alternatives as balanced, then lower_exposure. Check the frontend still selects the right default.

### 2.5 Frontend crypto tests fail on Node 18
- `frontend/src/lib/crypto.test.ts` fails with `crypto is not defined`. Upgrade WSL to Node 20, as the spec requires, or provide `globalThis.crypto` in the test setup.

### 2.6 Map may be blank in `make demo`
- **Where:** the CSP in `backend/waykin/main.py`, lines 35–36 (A4).
- **Do:** run `make demo` and open the browser console. If MapLibre's workers are blocked, add `worker-src 'self' blob:`.
- **Accept:** the map renders in `make demo` with no CSP errors.

---

## 3. P1 — accounts and families

### 3.1 Sign up, log in, log out
**Privacy-first design.** The server stores only what login needs: an account id, a display name, a login identifier and a password hash. It stores no location, no route history and no contact list.

- **Storage:** SQLite at `DATA_DIR/app.sqlite` (gitignored), using Python's built-in `sqlite3` with no ORM. This is the project's first persistent store, so record it in `docs/threat-model.md`.
- **Password hashing:** argon2id through `argon2-cffi`. Only A4 edits `pyproject.toml`, so request the package.
- **Endpoints** (new, so they need a contract request):
  - `POST /api/account` with `{display_name (1–40), login (email or username), password (≥ 10)}`, returning 201 `{account_id, display_name}`.
  - `POST /api/session` with `{login, password}`, returning 204 and setting a session cookie.
  - `DELETE /api/session` (log out) and `GET /api/account` (who am I).
  - `DELETE /api/account`, which deletes the account and its family memberships, and returns 204.
- **Session cookie:** `HttpOnly; Secure; SameSite=Strict`. Use `Path=/api/` only if every route endpoint ignores cookies; it's cleaner to set the cookie once per path, `/api/account`, `/api/families` and `/api/journeys`, so it never reaches `/api/routes`. Store only a sha256 of the session token on the server.
- **Rate limit** login attempts per IP and per login (for example 5 a minute). Error messages must not reveal whether a login exists.
- **Frontend:** a `/signup` page, a `/login` page, and an account menu with log out and delete account. **Planning a route must still work without an account.** Accounts are only for families.
- **Tests:** password never stored in plain text; wrong password gives the same error as an unknown login; the session cookie is never sent with `/api/routes` (check the `Path`); deleting an account removes its rows.

### 3.2 Families and invitations
**The idea:** a family is a small group, at most 8 people, that shares one secret **family key**. Location updates are end-to-end encrypted with keys only family members hold. The server sees who is in which family, but never anyone's location.

**Keys (WebCrypto, client side, extending `frontend/src/lib/crypto.ts`, A4's folder):**
- Each member's device generates an ECDH P-256 key pair when they log in. The public key goes to the server; the private key stays in IndexedDB as a non-extractable key.
- The family creator generates a 256-bit AES-GCM **family key**. For each member, the family key is *wrapped* (encrypted) with that member's public key and stored on the server as an opaque blob. The server can't unwrap it.

**Inviting someone (proposed flow):**
1. A member taps **Invite**. The client calls `POST /api/families/{id}/invites`, and the server returns a single-use `invite_token` that expires after 24 hours. Store only its hash.
2. The client builds a link with the token **and the family key in the URL fragment**, which browsers never send to the server:
   `https://<host>/join/{family_id}#i={invite_token}&k={base64url(family_key)}`
3. The member shares it any way they like: text, a QR code shown on screen, or in person.
4. The invitee opens it, signs up or logs in, and the client calls `POST /api/families/{id}/join` with `{invite_token, public_key}`. It then wraps the family key with its own public key and uploads that.
5. Existing members see "Sam joined the family". Any member can see the member list; only the family owner can remove people.

**Removing a member:** the owner removes them, then creates a **new family key**, wraps it for each remaining member, and uploads the new wrapped keys. Journeys started after that use the new key, so the removed person can't read new locations.

**Endpoints:** `POST /api/families`, `GET /api/families` (mine), `GET /api/families/{id}` (members and display names), `POST /api/families/{id}/invites`, `POST /api/families/{id}/join`, `DELETE /api/families/{id}/members/{account_id}` (owner, or yourself to leave), `PUT /api/families/{id}/keys` (upload rewrapped keys).

**Tests:** an invite works once only; an expired invite is rejected; a non-member gets 404, not 403, so family ids can't be probed; the server database never contains a raw family key; a removed member gets 404 on the family.

### 3.3 Family view
- **Route:** `/family` (rewrite `FamilyPage.tsx`, which is currently a placeholder).
- **Shows:** each member, with **Walking now** or **Not sharing**. Walking members show a live dot on the map, their route, an ETA and a status. Tapping one opens a full-screen follow view.
- **How live updates arrive:**
  - The walker starts a journey with `POST /api/journeys` and `{family_id}`. The client creates a per-journey key, wraps it with the family key, and sends the wrapped key in the request.
  - The server announces the journey on a new **family stream**, `WS /api/families/{id}/stream`, authenticated by the session in the first message. Its events: `journey.started {journey_id, walker_display_name, wrapped_key}`, `journey.ended {journey_id, reason}`, `member.joined`, `member.left`.
  - Family members' clients unwrap the journey key, then connect to the existing relay as viewers. The relay protocol and encryption in B5 stay the same; only how the key is delivered changes.
- **Keep the existing share link,** so someone outside the family can still be sent a one-off link.
- **Tests:** a family member sees a new journey within 2 seconds; a non-member can't connect to the stream; the server never receives plaintext coordinates. Extend `tests/privacy/`.

---

## 4. P1 — location notices and family alerts

### 4.1 Location access notices (walker side)
- **Before the browser's permission prompt,** show a short explanation of who will see the location, for how long, and that the server can't read it. Then call `navigator.geolocation`.
- **If permission is denied,** show how to turn it on again and offer **demo mode** (`SimGeo`).
- **While sharing,** show a persistent bar: "Sharing live with your family · 2 viewing · Stop". The viewing count comes from a new relay message `{"type":"viewers","count":n}`, which the server already knows from its socket count.
- **Viewer arrives or leaves:** show a toast such as "Alex is now viewing your walk". The family stream knows display names, so the server only sends `{"type":"viewer_joined","display_name":…}` for family viewers. Show share-link viewers as "Someone with your link".
- **Stops automatically** on arrival, stop, or expiry, with a confirmation such as "Sharing ended".

### 4.2 Family alerts
The **walker's device** detects these and sends them inside the encrypted `WalkerUpdate`, as a new optional field `alert: {kind, ts}`. That way the server never learns why an alert happened.

| Kind | Rule (make the defaults constants) | Viewer sees |
| --- | --- | --- |
| `arrived` | within 40 m of the destination | "Sam arrived" |
| `stopped` | moved less than 25 m in 5 minutes, away from the start or destination | "Sam hasn't moved for 5 minutes" |
| `off_route` | more than 75 m from the route for 60 seconds | "Sam is off the planned route" |
| `overdue` | now > start + ETA × 1.5 + 5 min | "Sam is later than expected" |
| `rerouted` | rerouted around a closure | "Sam's route changed around a closure" |
| `duress` | walker ends the walk with a **duress PIN** set in settings; their screen shows a normal "Sharing ended" | urgent alert with last location |
| `signal_lost` | **server-side**: no message from the walker for 2 minutes during a journey. The relay sends `{"type":"walker_silent","since":…}` to viewers, using only timing, never location | "We haven't heard from Sam's phone for 2 minutes" |

- **Delivery:** an in-app banner, a sound and vibration. Also send a system notification through the browser's Notification API while the family page is open, including in a background tab, after asking for permission.
- **Apps that are fully closed:** Web Push is an optional P2 item, because the spec listed it as out of scope. If approved, use VAPID with `pywebpush` (A4 adds the package). The push carries **no location**, only "Open WayKin: an update about Sam", and the app decrypts details once opened.
- **Wording:** factual and calm. Never use banned words, and never imply danger.
- **Tests:** unit-test each rule with `SimGeo` traces; a duress end looks identical to a normal end on the walker's screen and to the server; `walker_silent` fires after the timeout and contains no coordinates.

### 4.3 Activity log (on the device only)
- **Where:** a **History** page listing past journeys (date, duration, from/to street names, alerts raised) and family events (who joined, who viewed).
- **Storage:** IndexedDB on the device only. The server keeps no history. Provide **Clear history** and auto-delete after 30 days by default.
- **Tests:** clearing removes everything, and nothing in the log is sent to the server.

---

## 5. P1 — complete the core demo and the evidence

### 5.1 Walk screen (`WalkPage.tsx`, currently a placeholder)
Follow the original A1 spec: a live position (real GPS or `SimGeo` at 5× speed in demo mode), a route line, ETA, and the hazard stream. When a closure touches the route, call `POST /api/routes/reroute` and send the new route to the relay. Then add the notices and alerts from section 4.

### 5.2 Demo presets
Pick 3 start/end pairs **on EPS data** whose expected outcomes are `recommend`, `abstain` and `reroute`. Put them in `backend/waykin/demo/presets.json`, where they're served with `DEMO_MODE=1`. Verify each one gives its expected outcome with `EXPOSURE_SOURCE=eps`.

### 5.3 Pitch numbers (run only after 2.1 is fixed)
From `backend/`, with the venv active:
```bash
export EXPOSURE_SOURCE=eps
python -m scripts.data.abstain_rate --trips 200 --radii 50,100,200
python -m scripts.data.radius_choice
python -m scripts.data.revalidate --trips 200 --draws 100
python -m scripts.data.holdout --trips 200
```
They write to `results/data/`, and each result records its source. An early run gave about 88% abstention (25 recommendations out of 200 trips). The official run should come from these scripts. **Real EPS numbers stay private until the team lead resolves the EPS terms question.**

### 5.4 Citywide scale test (supports the feasibility claim)
In a scratch folder, never in `data/build/`, build the graph and EPS exposure for all of Edmonton. Record build time, file sizes, median and 95th-percentile route time, and abstention rate in `results/data/scale.json`. The pitch line becomes "Our demo covers campus; the same code builds all of Edmonton in N minutes and plans a route in M ms."

### 5.5 Manipulation-resistance score (P2, the creativity feature)
For each recommendation, find the smallest number of fake reports, placed at the worst locations, that flips the decision. Do the same for abstentions: how many fake reports it takes to force a recommendation. Each location's effect on the simulation adds independently, so simulate only the injected location and add it to X, without a rebuild. Show "Holds against at least N fake reports" on the route card. Report the share of recommendations that survive 5 or more fake reports.

---

## 6. P2 — pitch and submission support
- `docs/continuation.md`: users, the EPS data-agreement path, automated daily refresh, scale numbers from 5.4, hosting cost, and the privacy model as an operational advantage (no location history to secure).
- `docs/judge-questions.md`: prepared answers to "why trust police data?", "doesn't this stigmatize areas?", "what about the EPS terms?", "why so many abstentions?", "who sees my location?".
- Help S2 with the written summary: goals, approach, results (the numbers from 5.3), and limits.
- Record a backup demo video of the full flow: plan, walk, closure, reroute, family alert.

---

## 7. Suggested order
1. Section 2 (P0 fixes). The demo is broken without 2.1.
2. 5.2 demo presets and 5.3 measurements. These are cheap and give the pitch its numbers.
3. 5.1 Walk screen, then 4.1 and 4.2 location notices and alerts using the existing share link.
4. 3.1 to 3.3 accounts, families and the family view. This is the biggest piece, so start only once it's approved.
5. 5.4, 5.5 and section 6, as time allows. Anything not done by **H48** is cut.

## 8. Definition of done
- Plan, walk, closure, reroute and family alerts work end to end on EPS data in `make demo`. The three presets behave as labelled.
- Backend and frontend tests, typecheck and the banned-word lint all pass, and the privacy suite covers every new endpoint.
- `results/data/` holds abstention, radius choice and revalidation results, each with its source recorded.
- No coordinates in any log, no EPS data in git, and no cookie or token on `/api/routes`.
