"""Download the EPS Community Safety Data Portal occurrences (last 365 days) into data/raw/eps/ as one GeoJSON file.

python -m scripts.data.fetch_eps [--data-dir ../data]

Only the two columns WayKin reads are requested (Occurrence_Type_Group, Date_Reported), plus the published point,
already moved by EPS to the nearest intersection. The server returns at most 2000 features per request, so this pages.
Prints counts only, never coordinates.
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.parse
import urllib.request
from pathlib import Path

LAYER = "https://services9.arcgis.com/pkzvt2xlZJnPgk1Z/arcgis/rest/services/EPS_OCC_30DAY/FeatureServer/0/query"
FIELDS = "Occurrence_Type_Group,Date_Reported"
PAGE = 2000


def _get(params: dict) -> dict:
    url = f"{LAYER}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=120) as res:
        return json.load(res)


def fetch(out: Path) -> int:
    features, offset = [], 0
    while True:
        page = _get({"where": "1=1", "outFields": FIELDS, "outSR": 4326, "orderByFields": "OBJECTID",
                     "resultOffset": offset, "resultRecordCount": PAGE, "f": "geojson"})
        batch = page.get("features", [])
        features.extend(batch)
        offset += len(batch)
        print(f"  {offset} reports", flush=True)
        if not batch or not page.get("properties", {}).get("exceededTransferLimit"):
            break
    out.parent.mkdir(parents=True, exist_ok=True)
    for old in out.parent.glob("*"):        # EpsSource expects exactly one snapshot file
        if old != out and old.is_file():
            old.unlink()
    out.write_text(json.dumps({"type": "FeatureCollection", "features": features}), encoding="utf-8")
    return len(features)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--data-dir", default=os.getenv("DATA_DIR", "../data"))
    a = p.parse_args()
    n = fetch(Path(a.data_dir) / "raw" / "eps" / "eps_occurrences.geojson")
    print(f"saved {n} EPS reports to data/raw/eps/eps_occurrences.geojson")


if __name__ == "__main__":
    main()
