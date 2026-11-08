# WayKin data snapshot

A prebuilt `data/` folder, so the app runs without the ~15 minute city build in `docs/demo-runbook.md`. It is an
xz-compressed tar split into 49 MB parts (GitHub refuses files over 100 MB and warns over 50 MB).

**Restore** after every pull that changes `data-split/` (checks every part first, takes about a minute). From
`backend/` with the venv active, on Windows, macOS or Linux:

```bash
python -m scripts.data.snapshot restore
```

(`make restore-data` from the repo root does the same.) Then start the backend with `EXPOSURE_SOURCE=eps`.
Restoring replaces the snapshot's folders in `data/` and never touches `data/app.sqlite` (accounts).

## What's inside

| Path | What | Needed to |
| --- | --- | --- |
| `data/build/graph/` | Edmonton street graph with walking and driving (graph hash `e58f7d588f6e7d41`) | run |
| `data/build/exposure/eps/` | EPS exposure for driving routes, radius 100 m | run |
| `data/raw/eps/eps_occurrences.geojson` | 80,124 EPS reports, snapshot as of 2026-11-06 | rebuild exposure |
| `data/raw/osm/alberta-latest.osm.pbf` | Geofabrik Alberta extract, 2026-11-08 | rebuild the graph |

Walking pressure and the no-go zones are computed at server start from the exposure folder, so they need no files.
Not included: `data/app.sqlite` (accounts; the server recreates the demo account) and the synthetic exposure.

## Sending new data

After fetching new EPS reports or rebuilding the graph or exposure (runbook), repack and commit:

```bash
python -m scripts.data.snapshot pack      # from backend/; or make pack-data
git add data-split && git commit -m "data: snapshot as of <date>"
```

`pack` replaces the old parts and rewrites `SHA256SUMS`, and updates nothing else, so also update the table above.
Every new snapshot adds about 1 GB to the repository's history (GitHub refuses a single push over 2 GB), so send one
when the data has really changed, not on every build.

Parts made by `pack` and by the bash pipeline below are the same format, so either restores the other's:

```bash
tar -cf - --exclude='data/app.sqlite*' --exclude=data/build/exposure/synthetic data | xz -T0 -3 | \
  split -b 49M -d -a 2 - data-split/waykin-data.tar.xz.part- && \
(cd data-split && sha256sum waykin-data.tar.xz.part-* > SHA256SUMS)
```

The EPS reports are public Edmonton Police Service data; the disclaimer in the main README applies.
