import { strings } from "../copy/strings";

export function StabilityBadge({ drawsBetter, nDraws }: { drawsBetter: number; nDraws: number }) {
  return <p className="stability">{strings.holdsIn(drawsBetter, nDraws)}</p>;
}
