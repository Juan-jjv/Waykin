import { strings } from "../copy/strings";

export function RadiusSelect({
  radii,
  value,
  onChange,
}: {
  radii: number[];
  value: number;
  onChange: (next: number) => void;
}) {
  return (
    <section>
      <h2>{strings.catchment}</h2>
      <div className="segmented" role="radiogroup" aria-label={strings.catchment}>
        {radii.map((radius) => (
          <button
            key={radius}
            type="button"
            role="radio"
            aria-checked={radius === value}
            onClick={() => onChange(radius)}
          >
            {radius} m
          </button>
        ))}
      </div>
    </section>
  );
}
