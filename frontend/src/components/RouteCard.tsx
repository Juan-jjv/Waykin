import type { RouteOption } from "../api/tmp-types";
import { formatDiff, formatExposure, formatExtra, formatMinutes } from "../copy/format";
import { routeLabelText, strings } from "../copy/strings";
import { ROUTE_COLORS } from "../map/colors";
import { StabilityBadge } from "./StabilityBadge";

export function RouteCard({
  route,
  units,
  nDraws,
  selected,
  segmentsOpen,
  onSelect,
  onShowSegments,
  onStartWalk,
}: {
  route: RouteOption;
  units: string;
  nDraws: number;
  selected: boolean;
  segmentsOpen: boolean;
  onSelect: () => void;
  onShowSegments: () => void;
  onStartWalk: () => void;
}) {
  const label = routeLabelText[route.label];
  const extra = formatExtra(route.extra_minutes);
  const diff = formatDiff(route.exposure_diff_vs_fastest);

  return (
    <article className={selected ? "route-card selected" : "route-card"} style={{ borderLeftColor: ROUTE_COLORS[route.label] }}>
      <button type="button" className="route-select" onClick={onSelect}>
        <span className="route-label">
          <span className="swatch" style={{ background: ROUTE_COLORS[route.label] }} aria-hidden="true" />
          {label}
        </span>
        <span className="route-time">
          <strong>{formatMinutes(route.minutes)}</strong>
          {extra ? <small>{extra}</small> : null}
        </span>
      </button>
      <p className="exposure">{formatExposure(route.exposure)}</p>
      <p className="units">{units}</p>
      {diff ? <p className="diff">{diff}</p> : null}
      {route.draws_better != null ? <StabilityBadge drawsBetter={route.draws_better} nDraws={nDraws} /> : null}
      <p className="explanation">{route.explanation}</p>
      <div className="card-actions">
        <button
          type="button"
          className="btn-quiet"
          aria-pressed={segmentsOpen}
          onClick={onShowSegments}
        >
          {strings.showSegments}
        </button>
      </div>
      {selected ? (
        <button type="button" className="btn-primary" onClick={onStartWalk}>
          {strings.startWalk}
        </button>
      ) : null}
    </article>
  );
}
