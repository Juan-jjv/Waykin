"""Default radius draft (spec A2.8): python -m scripts.data.radius_choice

Reads results/data/abstention.json (run abstain_rate with --radii 50,100,200 first) and writes a short
results/data/radius_choice.md. The suggestion is only a draft: C2 makes the final call.
"""
from __future__ import annotations

import argparse
import json

from waykin import constants as C


def render(res: dict) -> str:
    if not res.get("by_radius"):
        raise SystemExit("abstention.json has no per-radius results: rerun abstain_rate with --radii 50,100,200")
    n = res["n_planned"]
    agree = res["agrees_with_majority"]
    radii = sorted(res["by_radius"], key=int)
    # The radius that most often agrees with the others is the least dependent on this one modelling choice.
    # Ties stay with the current default.
    pick = max(radii, key=lambda r: (agree.get(r, 0), int(r) == C.DEFAULT_RADIUS_M))
    lines = [f"# Default radius (draft for C2), measured on {res['source']} data, {n} trips", "",
             "| Radius | Recommended | Abstained | Agrees with the majority of radii |", "| --- | --- | --- | --- |"]
    for r in radii:
        outcomes = res["by_radius"][r]
        recommended = sum(v for k, v in outcomes.items() if k.startswith("recommend"))
        lines.append(f"| {r} m | {recommended} | {n - recommended} | {agree.get(r, 0)} of {n} |")
    lines += ["", f"The decision changed with the radius on {res['n_radius_sensitive']} of {n} trips.",
              f"Suggested default: **{pick} m**, the radius that most often agrees with the others."]
    if res["source"] == "synthetic":
        lines.append("Synthetic data: this checks the method and says nothing about Edmonton.")
    return "\n".join(lines) + "\n"


def main() -> None:
    from scripts.data._state import results_dir

    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--results-dir", default=None)
    a = p.parse_args()
    d = results_dir(a.results_dir)
    source = d / "abstention.json"
    if not source.exists():
        raise SystemExit("results/data/abstention.json not found: run scripts.data.abstain_rate first")
    (d / "radius_choice.md").write_text(render(json.loads(source.read_text(encoding="utf-8"))), encoding="utf-8")
    print(f"wrote {d / 'radius_choice.md'}")


if __name__ == "__main__":
    main()
