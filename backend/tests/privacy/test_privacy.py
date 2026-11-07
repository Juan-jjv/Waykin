"""One test (or group) per privacy promise in the pitch (A4.11). docs/threat-model.md links here."""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from starlette.websockets import WebSocketDisconnect

from waykin.api.deps import mock

REPO = Path(__file__).resolve().parents[3]
KEY = bytes(range(32))


# ------------------------------------------------------------ helpers
def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def aes_env(key: bytes, journey_id: str, seq: int, upd: dict, iv: bytes | None = None) -> dict:
    """A real AES-GCM envelope, byte-compatible with frontend/src/lib/crypto.ts."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    iv = iv if iv is not None else os.urandom(12)
    ct = AESGCM(key).encrypt(iv, json.dumps(upd).encode(), f"waykin:v1:{journey_id}:{seq}".encode())
    return {"v": 1, "seq": seq, "iv": b64u(iv), "ct": b64u(ct)}


def aes_open(key: bytes, journey_id: str, env: dict) -> dict:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    def dec(s: str) -> bytes:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    aad = f"waykin:v1:{journey_id}:{env['seq']}".encode()
    return json.loads(AESGCM(key).decrypt(dec(env["iv"]), dec(env["ct"]), aad))


def walker_update(lat: float = 53.52013, lon: float = -113.51234, **kw) -> dict:
    u = {"lat": lat, "lon": lon, "accuracy_m": 5.0, "ts": 1_762_480_000_000, "status": "walking", "eta_min": 9.5}
    u.update(kw)
    return u


def new_journey(client) -> dict:
    r = client.post("/api/journeys", json={})
    assert r.status_code == 201, r.text
    return r.json()


def ws(client, jid):
    return client.websocket_connect(f"/api/relay/{jid}")


def auth(sock, role: str, token: str) -> dict:
    sock.send_json({"type": "auth", "role": role, "token": token})
    return sock.receive_json()


def close_code(sock) -> int:
    """Read until the server closes the socket; return the close code."""
    try:
        while True:
            sock.receive_text()
    except WebSocketDisconnect as e:
        return e.code


# ------------------------------------------------------------ 1. the server never sees family locations
def test_e2ee_server_holds_only_ciphertext(client):
    j = new_journey(client)
    jid = j["journey_id"]
    st = client.app.state.waykin
    upd = walker_update(route={"route_id": "abc", "label": "fastest", "geometry": [[53.52, -113.52]]})
    with ws(client, jid) as w, ws(client, jid) as v:
        auth(w, "walker", j["walker_token"])
        auth(v, "viewer", j["viewer_token"])
        w.send_json({"type": "loc", "env": aes_env(KEY, jid, 1, upd)})
        got = v.receive_json()
        assert aes_open(KEY, jid, got["env"]) == upd           # the viewer can decrypt...
        held = st.journeys.get(jid).latest                      # ...the server holds only the envelope
        assert '"lat"' not in held and "53.52" not in held
        assert set(json.loads(held)) == {"type", "env"}
        assert '"lat"' not in repr(vars(st.journeys.get(jid)))
        w.send_json({"type": "loc", "plain": upd})              # plaintext is refused in e2ee mode
        assert close_code(w) == 4400
    assert '"lat"' not in (st.journeys.get(jid).latest or "")


def test_ciphertext_bound_to_journey_and_seq():
    from cryptography.exceptions import InvalidTag

    env = aes_env(KEY, "jid-a", 7, walker_update())
    with pytest.raises(InvalidTag):
        aes_open(KEY, "jid-b", env)                 # moved to another journey
    with pytest.raises(InvalidTag):
        aes_open(KEY, "jid-a", {**env, "seq": 8})   # renumbered


# ------------------------------------------------------------ 2. nothing is kept after a journey ends
def _assert_gone(client, jid):
    st = client.app.state.waykin
    assert jid not in st.journeys and st.journeys.get(jid) is None
    assert jid not in st.relay.rooms


@pytest.mark.parametrize("how", ["end", "delete", "expiry"])
def test_purged_after_journey_ends(client, how):
    j = new_journey(client)
    jid = j["journey_id"]
    st = client.app.state.waykin
    with ws(client, jid) as w, ws(client, jid) as v:
        auth(w, "walker", j["walker_token"])
        auth(v, "viewer", j["viewer_token"])
        w.send_json({"type": "loc", "env": aes_env(KEY, jid, 1, walker_update())})
        v.receive_text()
        assert st.journeys.get(jid).latest is not None
        if how == "end":
            w.send_json({"type": "end", "reason": "stopped"})
        elif how == "delete":
            r = client.delete(f"/api/journeys/{jid}", headers={"Authorization": f"Bearer {j['walker_token']}"})
            assert r.status_code == 204
        else:
            st.journeys.get(jid).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            client.portal.call(st.relay.sweep)
        ended = v.receive_json()
        assert ended == {"type": "ended", "reason": "expired" if how == "expiry" else "stopped"}
        assert close_code(v) == 4410
        assert close_code(w) == 4410
    _assert_gone(client, jid)
    with ws(client, jid) as again:
        again.send_json({"type": "auth", "role": "viewer", "token": j["viewer_token"]})
        assert close_code(again) == 4404


def test_demo_reset_purges_everything(make_client):
    c = make_client(DEMO_MODE=True)
    st = c.app.state.waykin
    j = new_journey(c)
    with ws(c, j["journey_id"]) as w:
        auth(w, "walker", j["walker_token"])
        w.send_json({"type": "loc", "env": aes_env(KEY, j["journey_id"], 1, walker_update())})
        assert c.post("/api/demo/reset").status_code == 204
        assert close_code(w) == 4410
    _assert_gone(c, j["journey_id"])
    assert len(st.journeys) == 0 and st.hazards.list() == []


# ------------------------------------------------------------ 3. expired and wrong tokens are rejected
@pytest.mark.parametrize("role,which", [("walker", None), ("walker", "viewer_token"), ("viewer", "walker_token")])
def test_wrong_token(client, role, which):
    j = new_journey(client)
    token = j[which] if which else "not-the-token"
    with ws(client, j["journey_id"]) as s:
        s.send_json({"type": "auth", "role": role, "token": token})
        assert close_code(s) == 4401


def test_expired_token(client):
    j = new_journey(client)
    client.app.state.waykin.journeys.get(j["journey_id"]).expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    with ws(client, j["journey_id"]) as v:
        v.send_json({"type": "auth", "role": "viewer", "token": j["viewer_token"]})
        assert close_code(v) == 4410


def test_delete_with_viewer_token(client):
    j = new_journey(client)
    r = client.delete(f"/api/journeys/{j['journey_id']}", headers={"Authorization": f"Bearer {j['viewer_token']}"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "forbidden"
    assert j["journey_id"] in client.app.state.waykin.journeys


def test_raw_tokens_never_stored(client):
    j = new_journey(client)
    stored = repr(vars(client.app.state.waykin.journeys.get(j["journey_id"])))
    assert j["walker_token"] not in stored and j["viewer_token"] not in stored


# ------------------------------------------------------------ 4. reroute requests aren't linked to a person
REROUTE = {"position": {"lat": 53.5201, "lon": -113.52}, "destination": {"lat": 53.52, "lon": -113.50}}


@pytest.mark.parametrize("extra", [{"journey_id": "abc"}, {"token": "abc"}, {"viewer_token": "abc"}])
def test_reroute_rejects_identifiers(client, extra):
    assert client.post("/api/routes/reroute", json={**REROUTE, **extra}).status_code == 422


class _Explodes:
    def __getattr__(self, name):
        raise AssertionError("reroute touched state.journeys")

    def __contains__(self, item):
        raise AssertionError("reroute touched state.journeys")


def _check_reroute_unlinked(c, body):
    real = c.app.state.waykin.journeys
    c.app.state.waykin.journeys = _Explodes()
    try:
        r = c.post("/api/routes/reroute", json=body, headers={"Authorization": "Bearer x", "Cookie": "session=abc"})
    finally:
        c.app.state.waykin.journeys = real
    assert r.status_code == 200, r.text
    assert "set-cookie" not in r.headers
    assert r.headers["cache-control"] == "no-store"


def test_reroute_unlinked_mock(client):
    _check_reroute_unlinked(client, REROUTE)


def test_reroute_unlinked_real(make_client, real_state):
    c = make_client(state=real_state)
    g = real_state.graph
    _check_reroute_unlinked(c, {"position": {"lat": float(g.node_lat[0]), "lon": float(g.node_lon[0])},
                                "destination": {"lat": float(g.node_lat[-1]), "lon": float(g.node_lon[-1])}})


# ------------------------------------------------------------ 5. only published intersection points are served
POINT_KEYS = {"location_id", "lat", "lon", "count", "by_category"}


def test_incidents_only_published_points_mock(client):
    src = {p["location_id"]: p for p in mock("incidents")["points"]}
    for p in client.get("/api/incidents").json()["points"]:
        assert set(p) == POINT_KEYS
        assert (p["lat"], p["lon"]) == (src[p["location_id"]]["lat"], src[p["location_id"]]["lon"])


def test_incidents_only_published_points_real(make_client, real_state):
    c = make_client(state=real_state)
    src = {str(r.location_id): (float(r.lat), float(r.lon)) for r in real_state.exposure.locations.itertuples(index=False)}
    pts = c.get("/api/incidents").json()["points"]
    assert pts
    for p in pts:
        assert set(p) == POINT_KEYS
        assert src[p["location_id"]] == (p["lat"], p["lon"])


# ------------------------------------------------------------ 6. EPS data is never committed
def test_gitignore_has_data_patterns():
    lines = (REPO / ".gitignore").read_text().splitlines()
    for pat in ["data/raw/", "data/build/", "*.npy", "*.npz", "*.parquet", ".env"]:
        assert pat in lines, pat


def test_no_data_files_tracked():
    if shutil.which("git") is None or not (REPO / ".git").exists():
        pytest.skip("not a git checkout")
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=False)
    if out.returncode != 0:
        pytest.skip("git ls-files failed")
    bad = [f for f in out.stdout.splitlines()
           if f.startswith("data/") or f.endswith((".npy", ".npz", ".parquet", ".csv", ".xlsx", ".geojson"))]
    assert bad == []


# ------------------------------------------------------------ 7. banned words (the frontend has npm run lint:words)
BANNED = re.compile(r"\b(" + "|".join(["s" + "afe", "s" + "afer", "s" + "afest", "s" + "afety", "uns" + "afe",
                                       "d" + "anger", "d" + "angerous"]) + r")\b", re.IGNORECASE)


def test_no_banned_words_backend():
    hits = []
    for p in (REPO / "backend" / "waykin").rglob("*"):
        if p.is_file() and p.suffix in (".py", ".json", ".yaml", ".md"):
            hits += [f"{p.relative_to(REPO)}:{i}" for i, line in enumerate(p.read_text(errors="ignore").splitlines(), 1)
                     if BANNED.search(line)]
    assert hits == []


# ------------------------------------------------------------ 8. no coordinates in logs
LAT, LON = 53.52013, -113.51234


def _needles() -> list[str]:
    out = {f"{x:.{d}f}" for x in (LAT, LON) for d in (4, 5)} | {repr(LAT), repr(LON)}
    return sorted(out)


def test_no_coordinates_in_logs(make_client, caplog):
    caplog.set_level(logging.DEBUG)
    c = make_client(DEMO_MODE=True)
    body = {"origin": {"lat": LAT, "lon": LON}, "destination": {"lat": LAT, "lon": LON}}
    c.post("/api/routes", json=body)
    c.post("/api/routes", json={**body, "radius_m": 75})          # validation error path
    c.post("/api/routes/reroute", json={"position": body["origin"], "destination": body["destination"]})
    c.post("/api/hazards", json={"kind": "closure", "lat": LAT, "lon": LON, "description": "x"})
    c.get("/api/incidents")
    j = new_journey(c)
    with ws(c, j["journey_id"]) as w:
        auth(w, "walker", j["walker_token"])
        w.send_json({"type": "loc", "env": aes_env(KEY, j["journey_id"], 1, walker_update(LAT, LON))})
        w.send_json({"type": "loc", "plain": walker_update(LAT, LON)})  # rejected: 4400
        close_code(w)
    pc = make_client(RELAY_PLAINTEXT=True)
    pj = new_journey(pc)
    with ws(pc, pj["journey_id"]) as w:
        auth(w, "walker", pj["walker_token"])
        w.send_json({"type": "loc", "plain": walker_update(LAT, LON)})
        w.send_json({"type": "end", "reason": "arrived"})
        close_code(w)

    access = [r.getMessage() for r in caplog.records if r.name == "waykin.access"]
    assert access, "expected access log records"
    for rec in caplog.records:
        text = rec.getMessage() + " " + repr(rec.args) + " " + (rec.exc_text or "")
        for n in _needles():
            assert n not in text, f"coordinate {n} leaked into log {rec.name}: {text[:200]}"
    assert not any(j["journey_id"] in m for m in access)  # route templates, never path values
