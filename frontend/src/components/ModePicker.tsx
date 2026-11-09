import type { ComponentType, CSSProperties } from "react";
import type { TravelMode } from "../api/types";
import { modeText, strings } from "../copy/strings";
import { CarIcon, WalkIcon } from "./icons";

const MODE_ICONS: Record<TravelMode, ComponentType> = { walk: WalkIcon, drive: CarIcon };

/** Walk / Drive segmented control. Hidden when the server can route only one mode. */
export function ModePicker({
  modes,
  mode,
  onChange,
}: {
  modes: TravelMode[];
  mode: TravelMode;
  onChange: (mode: TravelMode) => void;
}) {
  if (modes.length < 2) return null;
  const active = Math.max(0, modes.indexOf(mode));
  return (
    <div
      className="mode-switch"
      role="radiogroup"
      aria-label={strings.travelMode}
      style={{ "--count": modes.length, "--active": active } as CSSProperties}
    >
      <span className="mode-thumb" aria-hidden="true" />
      {modes.map((m) => {
        const ModeIcon = MODE_ICONS[m];
        return (
          <button
            key={m}
            type="button"
            role="radio"
            aria-checked={m === mode}
            className={m === mode ? "mode-opt on" : "mode-opt"}
            onClick={() => onChange(m)}
          >
            <ModeIcon />
            {modeText[m]}
          </button>
        );
      })}
    </div>
  );
}
