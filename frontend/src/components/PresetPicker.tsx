import type { DemoPreset } from "../api/tmp-types";
import { strings } from "../copy/strings";

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
    <section className="presets">
      <h2>{strings.presets}</h2>
      {presets.map((preset) => (
        <button
          key={preset.id}
          type="button"
          className={preset.id === selectedId ? "preset on" : "preset"}
          onClick={() => onSelect(preset)}
          aria-pressed={preset.id === selectedId}
        >
          <span className="preset-name">{preset.name}</span>
          <span className="preset-desc">{preset.description}</span>
        </button>
      ))}
    </section>
  );
}
