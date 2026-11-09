import type { DemoPreset } from "../api/types";
import { strings } from "../copy/strings";
import { CheckIcon, ChevronIcon } from "./icons";

export function PresetPicker({
  presets,
  selectedId,
  onSelect,
}: {
  presets: DemoPreset[];
  selectedId: string | null;
  onSelect: (preset: DemoPreset) => void;
}) {
  if (presets.length === 0) return null;

  return (
    <section className="presets" aria-labelledby="presets-title">
      <div className="section-head">
        <h2 id="presets-title" className="section-title">{strings.presets}</h2>
      </div>
      <div className="group">
        {presets.map((preset, index) => {
          const on = preset.id === selectedId;
          return (
            <button
              key={preset.id}
              type="button"
              className={on ? "preset on" : "preset"}
              onClick={() => onSelect(preset)}
              aria-pressed={on}
            >
              <span className="preset-tile" aria-hidden="true">{index + 1}</span>
              <span className="preset-text">
                <span className="preset-name">{preset.name}</span>
                <span className="preset-desc">{preset.description}</span>
              </span>
              <span className="preset-trail" aria-hidden="true">
                {on ? <CheckIcon size={18} /> : <ChevronIcon />}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
