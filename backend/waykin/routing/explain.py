"""Route explanations (spec A3.5). Phase 2: full version by H18."""
from __future__ import annotations

import math

from waykin import constants as C


def whole_minutes(x: float) -> int:
    """Round half up, matching the frontend's Math.round (Python's round() would give 2 for 2.5)."""
    return int(math.floor(x + 0.5))


def explanation_text(label: str, minutes: float, extra_min: float, diff_p50: float | None, p50: float) -> str:
    if label == "fastest":
        return f"Fastest option, {whole_minutes(minutes)} min. About {p50:.1f} {C.UNITS_SHORT}."
    if diff_p50 is not None and diff_p50 < 0:
        return (f"+{whole_minutes(extra_min)} min vs fastest. About {abs(diff_p50):.1f} fewer reported incidents "
                f"attributed to segments along this route (90 days).")
    return f"+{whole_minutes(extra_min)} min vs fastest. About the same number of reported incidents."
