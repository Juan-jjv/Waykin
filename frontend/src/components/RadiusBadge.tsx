import { useState } from "react";
import { formatRadiusDecision } from "../copy/format";
import { strings } from "../copy/strings";

export function RadiusBadge({ decisions }: { decisions: Record<string, string> | null }) {
  const [open, setOpen] = useState(false);
  const entries = Object.entries(decisions ?? {});

  return (
    <div className="radius-badge">
      <button type="button" className="radius-badge-btn" aria-expanded={open} onClick={() => setOpen((value) => !value)}>
        {strings.radiusChanges}
      </button>
      {open && entries.length > 0 ? (
        <ul className="radius-list">
          {entries.map(([radius, value]) => (
            <li key={radius}>
              <span>{radius} m</span>
              <span>{formatRadiusDecision(value)}</span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
