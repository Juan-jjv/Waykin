import { strings } from "../copy/strings";

export function StabilityBadge({ drawsBetter, nDraws }: { drawsBetter: number; nDraws: number }) {
  const share = nDraws > 0 ? Math.min(1, Math.max(0, drawsBetter / nDraws)) : 0;
  return (
    <div className="stability">
      <span className="meter" aria-hidden="true">
        <span className="meter-fill" style={{ width: `${share * 100}%` }} />
      </span>
      <p>{strings.holdsIn(drawsBetter, nDraws)}</p>
    </div>
  );
}
