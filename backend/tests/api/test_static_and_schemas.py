from __future__ import annotations

import pytest

from waykin import mocks
from waykin.schemas import IncidentsResponse, Meta, RoutesResponse


@pytest.mark.parametrize("name", ["routes_recommend", "routes_abstain", "routes_rerouted"])
def test_route_fixtures_validate(name):
    r = RoutesResponse.model_validate(mocks.load(name))
    labels = [x.label for x in r.routes]
    assert labels[0] == "fastest"
    for x in r.routes:
        assert len(x.geometry) == len(x.edge_ids) + 1
    if r.decision.status == "recommend":
        assert r.decision.recommended_route_id in {x.route_id for x in r.routes[1:]}


def test_other_fixtures_validate():
    Meta.model_validate(mocks.load("meta"))
    IncidentsResponse.model_validate(mocks.load("incidents"))


def test_spa_fallback(make_client, tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><title>WayKin</title>")
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")
    c = make_client(DEMO_MODE=True, FRONTEND_DIST=tmp_path)
    assert "WayKin" in c.get("/f/abc123").text
    assert c.get("/assets/app.js").text == "console.log(1)"
    assert "WayKin" in c.get("/../../etc/passwd").text
    assert c.get("/api/meta").status_code == 200
    r = c.get("/api/unknown")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
