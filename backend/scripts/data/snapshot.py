"""Pack or restore the committed data snapshot: python -m scripts.data.snapshot restore|pack

restore  checks every part in data-split/ against SHA256SUMS, then unpacks them into data/, replacing each folder the
         snapshot holds (the graph, the EPS exposure, the raw EPS reports, the OSM extract). data/app.sqlite (accounts)
         is never touched.
pack     writes data/build and data/raw (without the synthetic exposure) as an xz-compressed tar split into 49 MB parts,
         replacing the old parts, and rewrites SHA256SUMS. Commit data-split/ afterwards.

Same format as `make restore-data` in bash (cat parts | xz -d | tar -x), so either reads the other's parts. Standard
library only, so it runs the same on Windows, macOS and Linux.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import lzma
import shutil
import tarfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
PART_BYTES = 49 * 1024 * 1024        # GitHub refuses files over 100 MB and warns over 50 MB
PREFIX = "waykin-data.tar.xz.part-"
SUMS = "SHA256SUMS"
PACKED = ("build", "raw")            # under data/
SKIPPED = ("build/exposure/synthetic",)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def _parts(split_dir: Path) -> list[Path]:
    return sorted(split_dir.glob(PREFIX + "*"))


# ------------------------------------------------------------------ restore
class _Concat(io.RawIOBase):
    """The parts read back to back as one stream."""

    def __init__(self, paths: list[Path]):
        self._paths, self._f = list(paths), None

    def readable(self) -> bool:
        return True

    def readinto(self, b) -> int:
        while True:
            if self._f is None:
                if not self._paths:
                    return 0
                self._f = open(self._paths.pop(0), "rb")
            n = self._f.readinto(b)
            if n:
                return n
            self._f.close()
            self._f = None


def verify(split_dir: Path) -> list[Path]:
    sums = {}
    for line in (split_dir / SUMS).read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, name = line.split(maxsplit=1)
            sums[name.lstrip("*")] = digest
    parts = _parts(split_dir)
    names = [p.name for p in parts]
    if sorted(sums) != names:
        raise RuntimeError(f"parts and {SUMS} disagree: missing {sorted(set(sums) - set(names))}, "
                           f"unlisted {sorted(set(names) - set(sums))}")
    for p in parts:
        if _sha256(p) != sums[p.name]:
            raise RuntimeError(f"{p.name} is damaged or incomplete (checksum mismatch); pull again")
    return parts


def restore(repo: Path = REPO) -> list[str]:
    split_dir, data = repo / "data-split", repo / "data"
    parts = verify(split_dir)
    print(f"{len(parts)} parts verified; unpacking", flush=True)
    staging = data / ".restoring"
    shutil.rmtree(staging, ignore_errors=True)
    folders: set[Path] = set()
    with lzma.open(io.BufferedReader(_Concat(parts), 1 << 20)) as xz, tarfile.open(fileobj=xz, mode="r|") as tar:
        for member in tar:
            rel = Path(member.name)
            if rel.parts[:1] != ("data",) or ".." in rel.parts or member.issym() or member.islnk():
                raise RuntimeError(f"unexpected entry in the snapshot: {member.name}")
            if member.isfile():
                folders.add(rel.parent.relative_to("data"))
            tar.extract(member, staging, **({"filter": "data"} if hasattr(tarfile, "data_filter") else {}))
    folders = {f for f in folders if not any(a in folders for a in f.parents)}
    for folder in sorted(folders):
        target = data / folder
        if target.exists():
            shutil.rmtree(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        (staging / "data" / folder).replace(target)
    shutil.rmtree(staging, ignore_errors=True)
    restored = sorted(str(Path("data") / f).replace("\\", "/") for f in folders)
    for f in restored:
        print(f"  restored {f}")
    return restored


# ------------------------------------------------------------------ pack
class _XzSplitWriter(io.RawIOBase):
    """Compresses what it is given and writes it as numbered parts of PART_BYTES."""

    def __init__(self, out_dir: Path, preset: int):
        self._dir, self._xz = out_dir, lzma.LZMACompressor(preset=preset)
        self._index, self._f, self._left = 0, None, 0
        self.paths: list[Path] = []

    def writable(self) -> bool:
        return True

    def _emit(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            if self._f is None or self._left == 0:
                if self._f:
                    self._f.close()
                if self._index >= 100:
                    raise RuntimeError("snapshot needs more than 100 parts")
                path = self._dir / f"{PREFIX}{self._index:02d}"
                self._f, self._left = open(path, "wb"), PART_BYTES
                self.paths.append(path)
                self._index += 1
            n = min(self._left, len(view))
            self._f.write(view[:n])
            self._left -= n
            view = view[n:]

    def write(self, b) -> int:
        self._emit(self._xz.compress(bytes(b)))
        return len(b)

    def close(self) -> None:
        if not self.closed:
            self._emit(self._xz.flush())
            if self._f:
                self._f.close()
        super().close()


def pack(repo: Path = REPO, preset: int = 3) -> list[Path]:
    data, split_dir = repo / "data", repo / "data-split"
    roots = [data / p for p in PACKED if (data / p).is_dir()]
    if not (data / "build" / "graph" / "manifest.json").exists():
        raise FileNotFoundError("data/build/graph is missing: build or restore the data first")
    skipped = {(data / s).resolve() for s in SKIPPED}
    staging = split_dir / ".packing"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    started = time.time()
    out = _XzSplitWriter(staging, preset)
    with tarfile.open(fileobj=out, mode="w|", format=tarfile.PAX_FORMAT) as tar:
        for root in roots:
            for path in sorted(root.rglob("*")):
                if not path.is_file() or any(s == path.resolve() or s in path.resolve().parents for s in skipped):
                    continue
                arcname = path.relative_to(repo).as_posix()
                print(f"  {arcname} ({path.stat().st_size / 2**20:.0f} MB)", flush=True)
                tar.add(path, arcname=arcname, recursive=False)
    out.close()
    for old in _parts(split_dir):
        old.unlink()
    parts = []
    for p in out.paths:
        parts.append(p.replace(split_dir / p.name))
    staging.rmdir()
    sums = "".join(f"{_sha256(p)}  {p.name}\n" for p in parts)
    (split_dir / SUMS).write_bytes(sums.encode("utf-8"))
    total = sum(p.stat().st_size for p in parts) / 2**20
    print(f"{len(parts)} parts, {total:.0f} MB, in {time.time() - started:.0f} s -> data-split/")
    return parts


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["restore", "pack"])
    p.add_argument("--preset", type=int, default=3, help="xz level for pack (0-9; higher is smaller and slower)")
    a = p.parse_args()
    if a.command == "restore":
        restore()
        print("data/ restored. Start the backend with EXPOSURE_SOURCE=eps.")
    else:
        pack(preset=a.preset)
        print("Commit data-split/ to share it.")


if __name__ == "__main__":
    main()
