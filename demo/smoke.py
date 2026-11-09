#!/usr/bin/env python3
"""S1's smoke test (about 30 s): python demo/smoke.py --base http://localhost:8000

Checks the loop a judge will see, against a RUNNING server (mock, real or demo mode).
Parts that need later phases print SKIP instead of failing. Never prints coordinates.
Needs only the standard library plus `websockets` (installed with uvicorn[standard]).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request

from websockets.exceptions import ConnectionClosed
from websockets.sync.client import connect

RESULTS: list[tuple[str, str]] = []


def http(base, method, path, body=None, headers=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read()
            return r.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"null")


def check(name, ok, detail=""):
    RESULTS.append(("PASS" if ok else "FAIL", f"{name} {detail}".strip()))


def skip(name, why):
    RESULTS.append(("SKIP", f"{name} ({why})"))


def b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://localhost:8000")
    base = ap.parse_args().base.rstrip("/")
    ws_base = base.replace("http", "ws", 1)

    # 1. meta
    st, meta = http(base, "GET", "/api/meta")
    check("meta", st == 200 and meta and meta["provenance"]["disclaimer"], f"[{st}]")
    if st != 200:
        return report()
    w, s, e, n = meta["bbox"]

    # 2. routes: demo presets if present, otherwise one trip across the demo area
    presets = meta.get("demo_presets") or []
    trips = [(p["id"], p["origin"], p["destination"], p["expected"]) for p in presets] or \
            [("default", {"lat": s + (n - s) * 0.4, "lon": w + (e - w) * 0.4},
              {"lat": s + (n - s) * 0.6, "lon": w + (e - w) * 0.6}, None)]
    last_route = None
    for pid, o, d, expected in trips:
        st, r = http(base, "POST", "/api/routes", {"origin": o, "destination": d})
        ok = st == 200 and r["routes"] and r["provenance"]["source"] in ("eps", "synthetic")
        if ok and r["decision"]["recommended_route_id"] is not None:
            ok = r["decision"]["recommended_route_id"] != r["routes"][0]["route_id"]
        check(f"routes[{pid}]", ok, f"[{st}] {r['decision']['status'] if st == 200 else r}")
        if st == 200 and expected in ("recommend", "abstain"):
            check(f"routes[{pid}] matches expected", r["decision"]["status"] == expected,
                  f"expected {expected}, got {r['decision']['status']}")
        if st == 200:
            last_route = r

    # 3. reroute is stateless and works
    if last_route:
        dest = last_route["destination_snapped"]
        st, _ = http(base, "POST", "/api/routes/reroute", {"position": last_route["origin_snapped"], "destination": dest})
        check("reroute", st == 200, f"[{st}]")

    # 4. relay: walker -> viewer, then end purges the journey
    st, j = http(base, "POST", "/api/journeys", {})
    check("create journey", st == 201, f"[{st}]")
    if st == 201:
        url = f"{ws_base}/api/relay/{j['journey_id']}"
        update = {"lat": s, "lon": w, "accuracy_m": 5, "ts": 1, "status": "walking", "eta_min": 5}
        loc = {"type": "loc", "plain": update} if j["relay_mode"] == "plaintext" else \
              {"type": "loc", "env": {"v": 1, "seq": 1, "iv": b64(os.urandom(12)), "ct": b64(os.urandom(48))}}
        try:
            with connect(url) as walker, connect(url) as viewer:
                walker.send(json.dumps({"type": "auth", "role": "walker", "token": j["walker_token"]}))
                viewer.send(json.dumps({"type": "auth", "role": "viewer", "token": j["viewer_token"]}))
                ready = json.loads(walker.recv(timeout=5)), json.loads(viewer.recv(timeout=5))
                check("relay auth", all(m["type"] == "ready" for m in ready))
                walker.send(json.dumps(loc))
                got = json.loads(viewer.recv(timeout=5))
                check("relay delivers", got.get("type") == "loc", f"({j['relay_mode']})")
                walker.send(json.dumps({"type": "end", "reason": "arrived"}))
                check("relay end notifies", json.loads(viewer.recv(timeout=5)) == {"type": "ended", "reason": "arrived"})
        except (OSError, ConnectionClosed, TimeoutError) as ex:
            check("relay", False, type(ex).__name__)
        try:
            with connect(url) as again:
                again.send(json.dumps({"type": "auth", "role": "viewer", "token": j["viewer_token"]}))
                again.recv(timeout=5)
                check("journey purged after end", False, "reconnect was accepted")
        except ConnectionClosed as ex:
            check("journey purged after end", ex.rcvd is not None and ex.rcvd.code in (4404, 4410), f"[{ex.rcvd.code if ex.rcvd else '?'}]")

    # 5. hazards: public list; demo closure → reroute avoids it (Phase 3)
    st, hz = http(base, "GET", "/api/hazards")
    check("hazards public", st == 200, f"[{st}]")
    reroute_presets = [p for p in presets if p["expected"] == "reroute"]
    if not reroute_presets:
        skip("closure -> reroute", "no reroute preset yet: Phase 3")
    else:
        p = reroute_presets[0]
        st, h = http(base, "POST", f"/api/demo/trigger/{p['id']}")
        if st == 404:
            skip("closure -> reroute", "/api/demo/trigger not built yet: Phase 3")
        else:
            st, r = http(base, "POST", "/api/routes/reroute", {"position": p["origin"], "destination": p["destination"]})
            used = {e for route in r.get("routes", []) for e in route["edge_ids"]} if st == 200 else set()
            check("closure -> reroute avoids closed edges", st == 200 and not used & set(h["edge_ids"]), f"[{st}]")
            http(base, "POST", "/api/demo/reset")
    return report()


def report() -> int:
    for status, msg in RESULTS:
        print(f"{status:4}  {msg}")
    failed = sum(1 for s, _ in RESULTS if s == "FAIL")
    print(f"\n{'SMOKE FAILED' if failed else 'SMOKE OK'}: {failed} failed, "
          f"{sum(1 for s, _ in RESULTS if s == 'PASS')} passed, {sum(1 for s, _ in RESULTS if s == 'SKIP')} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
