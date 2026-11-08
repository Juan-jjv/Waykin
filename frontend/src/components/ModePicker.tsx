import type { TravelMode } from "../api/types";
import { modeText, strings } from "../copy/strings";

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
  return (
    <div className="mode-switch" role="radiogroup" aria-label={strings.travelMode}>
      {modes.map((m) => (
        <button
          key={m}
          type="button"
          role="radio"
          aria-checked={m === mode}
          className={m === mode ? "mode-opt on" : "mode-opt"}
          onClick={() => onChange(m)}
        >
          {modeText[m]}
        </button>
      ))}
    </div>
  );
}
