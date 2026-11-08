import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.data.build_exposure import build
from waykin.data.bundle import load_exposure, make_synthetic_bundle_for_tests
from waykin.routing.graph import load_graph
from waykin.routing.testing import make_grid_graph, write_graph_artifacts

REPO = Path(__file__).resolve().parents[3]
DRAWS = 20


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    write_graph_artifacts(make_grid_graph(), data / "build" / "graph")
    build(data, "synthetic", [50, 100], n_draws=DRAWS)
    return data


def out_dir(data):
    return data / "build" / "exposure" / "synthetic"


def graph_hash(data):
    return load_graph(data / "build" / "graph").graph_hash


def test_manifest_and_files(built):
    d = out_dir(built)
    m = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
    for key in ("source", "source_label", "as_of", "window_days", "radii", "n_draws", "seed", "kappa", "prior_strength",
                "n_published", "n_prior", "graph_hash", "category_preset", "built_at"):
        assert key in m
    assert m["radii"] == [50, 100] and m["n_draws"] == DRAWS
    for r in (50, 100):
        for name in (f"A_r{r}.npz", f"X_r{r}.npy", f"mean_r{r}.npy", f"observed_r{r}.npy"):
            assert (d / name).exists()


def test_locations_hold_published_rows_only(built):
    df = pd.read_parquet(out_dir(built) / "locations.parquet")
    assert set(df.columns) == {"location_id", "lat", "lon", "count", "counts_by_category"}
    assert df["count"].min() >= 1 and not df["location_id"].str.startswith("prior").any()


def test_daily_table_is_saved_and_loaded(built):
    b = load_exposure(built / "build" / "exposure", "synthetic", [100], graph_hash(built))
    assert list(b.daily.columns) == ["location_id", "date", "category", "count"]
    assert int(b.daily["count"].sum()) == int(b.locations["count"].sum())
    assert set(b.daily["location_id"]) <= set(b.locations["location_id"])


def test_load_round_trip_is_memory_mapped(built):
    b = load_exposure(built / "build" / "exposure", "synthetic", [100], graph_hash(built))
    assert b.radii == [100] and list(b.X) == [100] and isinstance(b.X[100], np.memmap)
    assert b.X[100].dtype == np.float32 and b.X[100].shape[1] == DRAWS
    assert abs(float(b.observed[100].sum()) - int(b.locations["count"].sum())) < 1e-2


def test_wrong_graph_hash_is_refused(built):
    with pytest.raises(RuntimeError, match="exposure built for a different graph; rerun build_exposure"):
        load_exposure(built / "build" / "exposure", "synthetic", [100], "0000000000000000")


def test_unbuilt_radius_is_refused(built):
    with pytest.raises(RuntimeError, match="not built"):
        load_exposure(built / "build" / "exposure", "synthetic", [200], graph_hash(built))


def test_rebuild_gives_identical_locations(built, tmp_path):
    write_graph_artifacts(make_grid_graph(), tmp_path / "build" / "graph")
    build(tmp_path, "synthetic", [100], n_draws=DRAWS)
    digests = {hashlib.sha256((out_dir(p) / "locations.parquet").read_bytes()).hexdigest() for p in (built, tmp_path)}
    assert len(digests) == 1


def test_build_prints_no_coordinates(tmp_path, capsys):
    write_graph_artifacts(make_grid_graph(), tmp_path / "build" / "graph")
    build(tmp_path, "synthetic", [100], n_draws=DRAWS)
    assert not re.search(r"-?\d{2,3}\.\d{3,}", capsys.readouterr().out)


def test_build_needs_the_graph(tmp_path):
    with pytest.raises(FileNotFoundError, match="graph not built"):
        build(tmp_path, "synthetic", [100], n_draws=DRAWS)


def test_server_state_loads_the_build(built):
    from waykin.config import Settings
    from waykin.main import build_state

    state, _ = build_state(Settings(WAYKIN_MOCK=False, DATA_DIR=built, LOAD_RADII="50,100", ADMIN_TOKEN="t"))
    assert state.exposure.radii == [50, 100] and state.exposure.source == "synthetic"


def test_test_bundle_has_prior_uncertainty_on_every_edge():
    g = make_grid_graph()
    b = make_synthetic_bundle_for_tests(g, radii=(100,))
    assert (b.X[100].std(axis=1) > 0).all()


def test_raw_and_build_data_are_gitignored():
    lines = (REPO / ".gitignore").read_text(encoding="utf-8").split()
    assert "data/raw/" in lines and "data/build/" in lines


def test_no_banned_words_in_the_data_package_including_yaml():
    banned = re.compile(r"\b(" + "|".join(["sa" + "fe", "sa" + "fer", "sa" + "fest", "sa" + "fety", "unsa" + "fe",
                                           "dan" + "ger", "dan" + "gerous"]) + r")\b", re.IGNORECASE)
    for path in (REPO / "backend" / "waykin" / "data").rglob("*"):
        if path.suffix in (".py", ".yaml"):
            assert not banned.search(path.read_text(encoding="utf-8")), path.name
