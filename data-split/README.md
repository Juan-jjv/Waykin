# WayKin data snapshot

A prebuilt `data/` folder, so the app runs without the ~15 minute city build in `docs/demo-runbook.md`. It is an
xz-compressed tar split into 49 MB parts (GitHub refuses files over 100 MB and warns over 50 MB).

**Restore** (from the repo root; checks every part first):

```bash
make restore-data
```

Then start the backend with `EXPOSURE_SOURCE=eps` (for example `EXPOSURE_SOURCE=eps make dev`).

## What's inside

| Path | What | Needed to |
| --- | --- | --- |
| `data/build/graph/` | Edmonton street graph with walking and driving (graph hash `e58f7d588f6e7d41`) | run |
| `data/build/exposure/eps/` | EPS exposure for driving routes, radius 100 m | run |
| `data/raw/eps/eps_occurrences.geojson` | 80,124 EPS reports, snapshot as of 2026-11-06 | rebuild exposure |
| `data/raw/osm/alberta-latest.osm.pbf` | Geofabrik Alberta extract, 2026-11-08 | rebuild the graph |

Walking pressure and the no-go zones are computed at server start from the exposure folder, so they need no files.
Not included: `data/app.sqlite` (accounts; the server recreates the demo account) and the synthetic exposure.

This snapshot matches the code on this branch. After a change to the graph or exposure build, rebuild (runbook), then
regenerate the parts:

```bash
rm -rf data-split/waykin-data.tar.xz.part-* && \
tar -cf - --exclude='data/app.sqlite*' --exclude=data/build/exposure/synthetic data | xz -T0 -3 | \
  split -b 49M -d -a 2 - data-split/waykin-data.tar.xz.part- && \
(cd data-split && sha256sum waykin-data.tar.xz.part-* > SHA256SUMS)
```

The EPS reports are public Edmonton Police Service data; the disclaimer in the main README applies.
