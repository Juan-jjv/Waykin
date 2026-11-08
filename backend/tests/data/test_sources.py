import hashlib
import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest
import yaml
from pyproj import Transformer

from waykin.data.pipeline import pivot_locations
from waykin.data.sources.base import (DAILY_COLUMNS, DATA_PKG, SOURCE_COLUMNS, category_config, get_source,
                                      validate_source_table)
from waykin.data.sources.eps import EpsConfigError, EpsSource
from waykin.data.sources.synthetic import SyntheticSource

BBOX = (-113.6, 53.4, -113.4, 53.6)
AS_OF = date(2026, 9, 30)
MAPPING = {"columns": {"lat": "Y", "lon": "X", "category": "Kind", "date": "Reported", "count": None},
           "point_wkt": None, "category_map": {"Assault": "assault", "Theft": "theft"}}


def graph_bbox(g):
    return (float(g.node_lon.min()), float(g.node_lat.min()), float(g.node_lon.max()), float(g.node_lat.max()))


def eps_source(tmp_path, rows=None, mapping=MAPPING):
    """A made-up snapshot with invented headers, written to a temporary folder. Not EPS data."""
    raw = tmp_path / "raw" / "eps"
    raw.mkdir(parents=True)
    if rows is None:
        rows = [
            ("Assault", 53.51, -113.51, AS_OF, "10 Fake Street"),
            ("Assault", 53.51, -113.51, AS_OF - timedelta(days=5), "10 Fake Street"),
            ("Theft", 53.51, -113.51, AS_OF - timedelta(days=89), "10 Fake Street"),
            ("Theft", 53.52, -113.52, AS_OF - timedelta(days=90), "too old"),
            ("Bylaw", 53.52, -113.52, AS_OF, "not a mapped category"),
            ("Theft", 53.9, -113.52, AS_OF, "outside the box"),
        ]
    pd.DataFrame(rows, columns=["Kind", "Y", "X", "Reported", "Address"]).to_csv(raw / "snapshot.csv", index=False)
    path = tmp_path / "mapping.yaml"
    path.write_text(yaml.safe_dump(mapping), encoding="utf-8")
    return EpsSource(tmp_path, mapping_path=path)


def test_synthetic_matches_contract(grid):
    bbox = graph_bbox(grid)
    src = SyntheticSource(".", graph=grid)
    df = src.load(bbox, None)
    validate_source_table(df, bbox)
    assert set(df.columns) == set(SOURCE_COLUMNS)
    assert df["location_id"].str.startswith("syn-").all()
    assert src.label == "Synthetic data (demo)" and src.as_of() == date(2026, 10, 31)


def test_synthetic_is_byte_for_byte_deterministic(grid, tmp_path):
    digests = []
    for i in range(2):
        path = tmp_path / f"{i}.parquet"
        pivot_locations(SyntheticSource(".", graph=grid).load(graph_bbox(grid), None)).to_parquet(path, index=False)
        digests.append(hashlib.sha256(path.read_bytes()).hexdigest())
    assert digests[0] == digests[1]


def test_synthetic_respects_category_filter(grid):
    df = SyntheticSource(".", graph=grid).load(graph_bbox(grid), ["assault"])
    assert set(df["category"]) == {"assault"}


def test_presets_use_known_categories():
    cfg = category_config()
    assert set(cfg.presets["person_directed"]) <= set(cfg.categories) and cfg.active_preset in cfg.presets


@pytest.mark.parametrize("change, message", [
    (lambda d: d.assign(extra=1), "columns"),
    (lambda d: d.assign(count=0), "integer"),
    (lambda d: d.assign(count=1.5), "integer"),
    (lambda d: d.assign(lat=10.0), "outside"),
    (lambda d: d.assign(period_start=d["period_end"]), "span"),
    (lambda d: pd.concat([d, d]), "duplicate"),
    (lambda d: d.assign(lat="53.5"), "float"),
])
def test_validate_rejects_bad_tables_without_coordinates(grid, change, message):
    bbox = graph_bbox(grid)
    good = SyntheticSource(".", graph=grid).load(bbox, None)
    with pytest.raises(ValueError, match=message) as err:
        validate_source_table(change(good), bbox)
    assert "53." not in str(err.value) and "113." not in str(err.value)


def test_get_source_rejects_unknown_name(tmp_path):
    with pytest.raises(ValueError):
        get_source("other", tmp_path)


def test_eps_missing_snapshot_message(tmp_path):
    with pytest.raises(FileNotFoundError, match="EPS snapshot not found in data/raw/eps; use EXPOSURE_SOURCE=synthetic"):
        EpsSource(tmp_path).load(BBOX, None)


def test_eps_refuses_an_unfilled_mapping(tmp_path):
    (tmp_path / "raw" / "eps").mkdir(parents=True)
    (tmp_path / "raw" / "eps" / "s.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    (tmp_path / "m.yaml").write_text("columns: {category: null, date: null}\ncategory_map: {}\n", encoding="utf-8")
    with pytest.raises(EpsConfigError, match="not filled in"):
        EpsSource(tmp_path, mapping_path=tmp_path / "m.yaml").load(BBOX, None)


def test_shipped_mapping_is_valid_and_targets_every_category():
    mapping = yaml.safe_load((DATA_PKG / "eps_columns.yaml").read_text(encoding="utf-8"))
    assert set(mapping["category_map"].values()) == set(category_config().categories)
    assert mapping["columns"]["category"] and mapping["columns"]["date"]


def test_eps_converts_geojson_points_from_the_declared_crs(tmp_path):
    raw = tmp_path / "raw" / "eps"
    raw.mkdir(parents=True)
    x, y = Transformer.from_crs("EPSG:4326", "EPSG:3857", always_xy=True).transform(-113.51, 53.51)
    feature = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [x, y]},
               "properties": {"Kind": "Theft", "Reported": "2026/09/30", "Street": "1 FAKE ST/2 FAKE AVE"}}
    (raw / "s.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": [feature],
                                               "crs": {"type": "name", "properties": {"name": "EPSG:3857"}}}), encoding="utf-8")
    mapping = {"columns": {"category": "Kind", "date": "Reported"}, "category_map": {"Theft": "theft"}}
    (tmp_path / "m.yaml").write_text(yaml.safe_dump(mapping), encoding="utf-8")
    df = EpsSource(tmp_path, mapping_path=tmp_path / "m.yaml").load(BBOX, None)
    validate_source_table(df, BBOX)
    assert np.isclose(df["lat"].iloc[0], 53.51) and np.isclose(df["lon"].iloc[0], -113.51)
    assert set(df.columns) == set(SOURCE_COLUMNS) and "FAKE" not in df.to_csv()


def test_eps_reports_a_column_missing_from_the_file(tmp_path):
    bad = {**MAPPING, "columns": {**MAPPING["columns"], "date": "NoSuchColumn"}}
    with pytest.raises(EpsConfigError, match="NoSuchColumn"):
        eps_source(tmp_path, mapping=bad).load(BBOX, None)


def test_eps_aggregates_filters_and_drops_free_text(tmp_path):
    src = eps_source(tmp_path)
    df = src.load(BBOX, None)
    validate_source_table(df, BBOX)
    assert set(df.columns) == set(SOURCE_COLUMNS)              # no address-like column survives
    assert "Fake" not in df.to_csv()
    assert src.as_of() == AS_OF
    assert dict(zip(df["category"], df["count"])) == {"assault": 2, "theft": 1}
    assert df["location_id"].nunique() == 1 and df["location_id"].iloc[0].startswith("eps-")


def test_eps_daily_splits_the_same_reports_by_day(tmp_path):
    src = eps_source(tmp_path)
    daily = src.daily(BBOX, None)
    assert list(daily.columns) == DAILY_COLUMNS and "Fake" not in daily.to_csv()
    assert daily["count"].sum() == src.load(BBOX, None)["count"].sum()
    assert set(daily["date"]) == {AS_OF, AS_OF - timedelta(days=5), AS_OF - timedelta(days=89)}


def test_synthetic_daily_matches_load_and_stays_in_the_window(grid):
    src = SyntheticSource(".", graph=grid)
    bbox = graph_bbox(grid)
    table, daily = src.load(bbox, None), src.daily(bbox, None)
    assert list(daily.columns) == DAILY_COLUMNS
    totals = daily.groupby(["location_id", "category"])["count"].sum()
    assert totals.to_dict() == table.set_index(["location_id", "category"])["count"].to_dict()
    end = src.as_of()
    assert daily["date"].max() <= end and daily["date"].min() > end - timedelta(days=90)
    assert daily.equals(src.daily(bbox, None))


def test_eps_keeps_points_as_published(tmp_path):
    df = eps_source(tmp_path).load(BBOX, None)
    assert np.isclose(df["lat"].iloc[0], 53.51) and np.isclose(df["lon"].iloc[0], -113.51)


def test_eps_reads_points_from_wkt_and_counts(tmp_path):
    raw = tmp_path / "raw" / "eps"
    raw.mkdir(parents=True)
    pd.DataFrame({"Kind": ["Theft"], "Point": ["POINT (-113.51 53.51)"], "Reported": [str(AS_OF)], "N": [4]}).to_csv(
        raw / "s.csv", index=False)
    mapping = {"columns": {"category": "Kind", "date": "Reported", "count": "N"}, "point_wkt": "Point",
               "category_map": {"Theft": "theft"}}
    (tmp_path / "m.yaml").write_text(yaml.safe_dump(mapping), encoding="utf-8")
    df = EpsSource(tmp_path, mapping_path=tmp_path / "m.yaml").load(BBOX, None)
    assert df["count"].tolist() == [4] and np.isclose(df["lat"].iloc[0], 53.51)
