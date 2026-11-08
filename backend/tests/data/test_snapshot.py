import os

import pytest

from scripts.data import snapshot


def make_repo(root):
    files = {
        "data/build/graph/manifest.json": b'{"graph_hash": "abc"}',
        "data/build/graph/edges.npy": os.urandom(300_000),
        "data/build/exposure/eps/X_r100.npy": os.urandom(500_000),
        "data/raw/eps/eps_occurrences.geojson": b'{"type": "FeatureCollection", "features": []}',
    }
    for rel, body in files.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(body)
    (root / "data/build/exposure/synthetic").mkdir(parents=True)
    (root / "data/build/exposure/synthetic/X_r100.npy").write_bytes(b"not packed")
    (root / "data/app.sqlite").write_bytes(b"accounts")
    return files


def test_pack_then_restore_round_trip(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "PART_BYTES", 100_000)
    files = make_repo(tmp_path)
    parts = snapshot.pack(tmp_path, preset=0)
    assert len(parts) > 3 and all(p.stat().st_size <= 100_000 for p in parts)
    assert not (tmp_path / "data-split" / ".packing").exists()

    (tmp_path / "data/build/graph/edges.npy").write_bytes(b"stale")
    (tmp_path / "data/build/graph/old_only.npy").write_bytes(b"left over from an older build")
    (tmp_path / "data/app.sqlite").write_bytes(b"newer accounts")
    restored = snapshot.restore(tmp_path)

    assert restored == ["data/build/exposure/eps", "data/build/graph", "data/raw/eps"]
    for rel, body in files.items():
        assert (tmp_path / rel).read_bytes() == body
    assert not (tmp_path / "data/build/graph/old_only.npy").exists()
    assert (tmp_path / "data/app.sqlite").read_bytes() == b"newer accounts"
    assert (tmp_path / "data/build/exposure/synthetic/X_r100.npy").read_bytes() == b"not packed"


def test_repacking_replaces_the_old_parts(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "PART_BYTES", 100_000)
    make_repo(tmp_path)
    first = snapshot.pack(tmp_path, preset=0)
    (tmp_path / "data/build/exposure/eps/X_r100.npy").write_bytes(b"small now")
    second = snapshot.pack(tmp_path, preset=0)
    assert len(second) < len(first)
    assert sorted((tmp_path / "data-split").glob(snapshot.PREFIX + "*")) == second
    assert len((tmp_path / "data-split" / snapshot.SUMS).read_text().splitlines()) == len(second)


def test_damaged_or_missing_part_is_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(snapshot, "PART_BYTES", 100_000)
    make_repo(tmp_path)
    parts = snapshot.pack(tmp_path, preset=0)
    parts[1].write_bytes(parts[1].read_bytes()[:-10])
    with pytest.raises(RuntimeError, match="checksum mismatch"):
        snapshot.restore(tmp_path)
    parts[1].unlink()
    with pytest.raises(RuntimeError, match="missing"):
        snapshot.restore(tmp_path)
