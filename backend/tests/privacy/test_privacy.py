"""One test (or group) per privacy promise in the pitch (A4.11)."""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from waykin import mocks
from waykin.realtime.testing import aes_env, aes_open, auth, close_code, new_journey, send, walker_update

REPO = Path(__file__).resolve().parents[3]
KEY = bytes(range(32))
ADMIN = {"X-Admin-Token": "test-admin-token"}


def _ws(c, jid):
    return c.websocket_connect(f"/api/relay/{jid}")


# ------------------------------------------------------------ 1. the server never sees family locations
def test_e2ee_server_holds_only_ciphertext(client):
    j = new_journey(client)
    jid = j["journey_id"]
    state = client.app.state.waykin
    upd = walker_update(route={"route_id": "abc", "label": "fastest", "geometry": [[53.52, -113.52]]})
    with _ws(client, jid) as w, _ws(client, jid) as v:
        auth(w, "walker", j["walker_token"])
        auth(v, "viewer", j["viewer_token"])
        env = aes_env(KEY, jid, 1_762_480_000_000, upd, iv=bytes(range(12)))
        send(w, {"type": "loc", "env": env})
        got = v.receive_json()
        assert aes_open(KEY, jid, got["env"]) == upd  # the viewer can decrypt...

        held = state.journeys.get(jid).latest     # ...the server holds only envelope text
        assert held is not None and '"lat"' not in held and "53.52" not in held
        assert set(json.loads(held)) == {"type", "env"}
        for j_ in state.journeys._journeys.values():
            assert '"lat"' not in repr(vars(j_))
        assert '"lat"' not in repr(vars(state.relay))

        send(w, {"type": "loc", "plain": upd})
        assert close_code(w) == 4400
    assert '"lat"' not in (state.journeys.get(jid).latest or "")


def test_ciphertext_bound_to_journey_and_seq():
    pytest.importorskip("cryptography")
    from cryptography.exceptions import InvalidTag

    env = aes_env(KEY, "jid-a", 7, walker_update())
    with pytest.raises(InvalidTag):
        aes_open(KEY, "jid-b", env)
    with pytest.raises(InvalidTag):
        aes_open(KEY, "jid-a", {**env, "seq": 8})


# ------------------------------------------------------------ 2. nothing is kept after a journey ends
def _assert_gone(client, jid):
    st = client.app.state.waykin
    assert jid not in st.journeys
    assert st.journeys.get(jid) is None
    assert jid not in st.relay.walkers and jid not in st.relay.viewers
    assert st.relay.socket_count(jid) == 0


def _reconnect_code(client, j):
    with _ws(client, j["journey_id"]) as v:
        send(v, {"type": "auth", "role": "viewer", "token": j["viewer_token"]})
        return close_code(v)


@pytest.mark.parametrize("how", ["end", "delete", "expiry"])
def test_purged_after_journey_ends(client, how):
    j = new_journey(client)
    jid = j["journey_id"]
    st = client.app.state.waykin
    with _ws(client, jid) as w, _ws(client, jid) as v:
        auth(w, "walker", j["walker_token"])
        auth(v, "viewer", j["viewer_token"])
        send(w, {"type": "loc", "env": aes_env(KEY, jid, 1, walker_update())})
        v.receive_text()
        assert st.journeys.get(jid).latest is not None
        if how == "end":
            send(w, {"type": "end", "reason": "stopped"})
        elif how == "delete":
            r = client.delete(f"/api/journeys/{jid}", headers={"Authorization": f"Bearer {j['walker_token']}"})
            assert r.status_code == 204
        else:
            st.journeys.get(jid).expires_at = datetime.now(UTC) - timedelta(seconds=1)
            assert client.portal.call(st.relay.sweep_expired) == [jid]
        ended = v.receive_json()
        assert ended["type"] == "ended"
        assert ended["reason"] == {"end": "stopped", "delete": "stopped", "expiry": "expired"}[how]
        assert close_code(v) == 4410
        assert close_code(w) == 4410
    _assert_gone(client, jid)
    assert _reconnect_code(client, j) in (4404, 4410)


# ------------------------------------------------------------ 3. expired and wrong tokens are rejected
def test_wrong_token(client):
    j = new_journey(client)
    with _ws(client, j["journey_id"]) as w:
        send(w, {"type": "auth", "role": "walker", "token": "not-the-token"})
        assert close_code(w) == 4401


def test_viewer_token_as_walker(client):
    j = new_journey(client)
    with _ws(client, j["journey_id"]) as w:
        send(w, {"type": "auth", "role": "walker", "token": j["viewer_token"]})
        assert close_code(w) == 4401


def test_expired_token(client):
    j = new_journey(client)
    client.app.state.waykin.journeys.get(j["journey_id"]).expires_at = datetime.now(UTC) - timedelta(seconds=1)
    with _ws(client, j["journey_id"]) as v:
        send(v, {"type": "auth", "role": "viewer", "token": j["viewer_token"]})
        assert close_code(v) == 4410
    _assert_gone(client, j["journey_id"])


def test_delete_with_viewer_token(client):
    j = new_journey(client)
    r = client.delete(f"/api/journeys/{j['journey_id']}", headers={"Authorization": f"Bearer {j['viewer_token']}"})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "forbidden"
    assert j["journey_id"] in client.app.state.waykin.journeys


def test_raw_tokens_never_stored(client):
    j = new_journey(client)
    stored = repr(vars(client.app.state.waykin.journeys.get(j["journey_id"])))
    assert j["walker_token"] not in stored and j["viewer_token"] not in stored


# ------------------------------------------------------------ 4. reroute requests aren't linked to a person
REROUTE = {"position": {"lat": 53.5201, "lon": -113.52}, "destination": {"lat": 53.52, "lon": -113.50}}


@pytest.mark.parametrize("extra", [{"journey_id": "abc"}, {"token": "abc"}, {"viewer_token": "abc"}])
def test_reroute_rejects_identifiers(client, extra):
    r = client.post("/api/routes/reroute", json={**REROUTE, **extra})
    assert r.status_code == 422


class _Explodes:
    def __getattr__(self, name):
        raise AssertionError("reroute touched state.journeys")

    def __contains__(self, item):
        raise AssertionError("reroute touched state.journeys")


def _check_reroute_unlinked(c):
    c.app.state.waykin.journeys = _Explodes()
    r = c.post("/api/routes/reroute", json=REROUTE,
               headers={"Authorization": "Bearer something", "Cookie": "session=abc"})
    assert r.status_code == 200, r.text
    assert "set-cookie" not in r.headers
    assert r.headers["cache-control"] == "no-store"


def test_reroute_unlinked_mock(client):
    _check_reroute_unlinked(client)


def test_reroute_unlinked_real(make_client, real_state):
    c = make_client(state=real_state, WAYKIN_MOCK=False)
    g = real_state.graph
    REROUTE_REAL = {"position": {"lat": float(g.node_lat[0]), "lon": float(g.node_lon[0])},
                    "destination": {"lat": float(g.node_lat[-1]), "lon": float(g.node_lon[-1])}}
    c.app.state.waykin.journeys = _Explodes()
    try:
        r = c.post("/api/routes/reroute", json=REROUTE_REAL)
    except NotImplementedError:
        pytest.skip("routing.service.plan not implemented yet")
    assert r.status_code == 200, r.text
    assert "set-cookie" not in r.headers


# ------------------------------------------------------------ 5. only intersection points are served
POINT_KEYS = {"location_id", "lat", "lon", "count", "by_category"}


def test_incidents_only_published_points_mock(client):
    src = {p["location_id"]: p for p in mocks.load("incidents")["points"]}
    for p in client.get("/api/incidents").json()["points"]:
        assert set(p) == POINT_KEYS
        s = src[p["location_id"]]
        assert (p["lat"], p["lon"]) == (s["lat"], s["lon"])


def test_incidents_only_published_points_real(make_client, real_state):
    c = make_client(state=real_state, WAYKIN_MOCK=False)
    locs = real_state.exposure.locations
    src = {str(r.location_id): (float(r.lat), float(r.lon)) for r in locs.itertuples(index=False)}
    pts = c.get("/api/incidents").json()["points"]
    for p in pts:
        assert set(p) == POINT_KEYS
        assert src[p["location_id"]] == (p["lat"], p["lon"])


# ------------------------------------------------------------ 6. EPS data is never committed
GITIGNORE_PATTERNS = ["data/raw/", "data/build/", "*.npy", "*.npz", "*.parquet", ".env"]


def test_gitignore_has_data_patterns():
    lines = (REPO / ".gitignore").read_text().splitlines()
    for pat in GITIGNORE_PATTERNS:
        assert pat in lines, pat


def test_no_data_files_tracked():
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("git not available")
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        pytest.skip("not a git checkout")
    files = out.stdout.splitlines()
    bad = [f for f in files if f.startswith("data/") or f.endswith((".npy", ".npz", ".parquet"))]
    assert bad == []


# ------------------------------------------------------------ 7. banned words (the CI job also runs npm lint:words)
BANNED = re.compile(r"\b(" + "|".join(["s" + "afe", "s" + "afer", "s" + "afest", "s" + "afety", "uns" + "afe",
                                       "d" + "anger", "d" + "angerous"]) + r")\b", re.IGNORECASE)


def _scan(root: Path, exts: tuple[str, ...]) -> list[str]:
    hits = []
    if not root.exists():
        return hits
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in exts and "node_modules" not in p.parts:
            for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1):
                if BANNED.search(line):
                    hits.append(f"{p.relative_to(REPO)}:{i}")
    return hits


def test_no_banned_words_backend():
    assert _scan(REPO / "backend" / "waykin", (".py", ".json", ".yaml", ".yml", ".md")) == []


def test_no_banned_words_frontend_lib():
    assert _scan(REPO / "frontend" / "src" / "lib", (".ts", ".tsx")) == []


# ------------------------------------------------------------ 8. no coordinates in logs
LAT, LON = 53.52013, -113.51234


def _coord_strings() -> list[str]:
    out = set()
    for x in (LAT, LON, 53.5201, 53.52):
        for d in (4, 5, 6):
            out.add(f"{x:.{d}f}")
        out.add(repr(x))
    return [s for s in out if len(s.split(".")[-1]) >= 4]


def test_no_coordinates_in_logs(make_client, caplog):
    caplog.set_level(logging.DEBUG)
    os.environ.pop("PYTHONWARNINGS", None)
    c = make_client(DEMO_MODE=True)
    body = {"origin": {"lat": LAT, "lon": LON}, "destination": {"lat": LAT, "lon": LON}}
    c.post("/api/routes", json=body)
    c.post("/api/routes", json={**body, "radius_m": 75})                      # validation error path
    c.post("/api/routes/reroute", json={"position": body["origin"], "destination": body["destination"]})
    c.post("/api/hazards", json={"kind": "closure", "lat": LAT, "lon": LON, "description": "x"})
    c.get("/api/incidents")
    j = new_journey(c)
    with _ws(c, j["journey_id"]) as w:
        auth(w, "walker", j["walker_token"])
        send(w, {"type": "loc", "env": aes_env(KEY, j["journey_id"], 1, walker_update(LAT, LON))})
        send(w, {"type": "loc", "plain": walker_update(LAT, LON)})  # rejected: 4400
        close_code(w)
    pc = make_client(RELAY_PLAINTEXT=True)
    pj = new_journey(pc)
    with _ws(pc, pj["journey_id"]) as w:
        auth(w, "walker", pj["walker_token"])
        send(w, {"type": "loc", "plain": walker_update(LAT, LON)})
        send(w, {"type": "end", "reason": "arrived"})
        close_code(w)

    assert caplog.records, "expected access log records"
    assert any(r.name == "waykin.access" for r in caplog.records)
    needles = _coord_strings()
    for rec in caplog.records:
        text = rec.getMessage() + " " + repr(rec.args) + " " + (rec.exc_text or "")
        for n in needles:
            assert n not in text, f"coordinate {n} leaked into log {rec.name}: {text[:200]}"
    access = [r.getMessage() for r in caplog.records if r.name == "waykin.access"]
    assert any("/api/relay/{journey_id}" in m for m in access)
    assert not any(j["journey_id"] in m for m in access)  # templates, not path params
