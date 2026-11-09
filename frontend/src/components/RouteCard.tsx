import type { CSSProperties } from "react";
import type { RouteOption } from "../api/types";
import { formatCount, formatDiff, formatDistance, formatExtra, formatMinutes } from "../copy/format";
import { routeLabelText, strings } from "../copy/strings";
import { ROUTE_COLORS } from "../map/colors";
import { ArrowDownIcon, CheckIcon, EqualIcon, PlayIcon, SegmentsIcon } from "./icons";
import { StabilityBadge } from "./StabilityBadge";

export function RouteCard({
  route,
  units,
  nDraws,
  selected,
  recommended = false,
  segmentsOpen,
  onSelect,
  onShowSegments,
  onStartWalk,
  startLabel = strings.startWalk,
  exposureNoun = strings.exposureNoun,
  index = 0,
}: {
  route: RouteOption;
  units: string;
  nDraws: number;
  selected: boolean;
  recommended?: boolean;
  segmentsOpen: boolean;
  onSelect: () => void;
  onShowSegments: () => void;
  onStartWalk: () => void;
  startLabel?: string;
  exposureNoun?: string;
  index?: number;
}) {
  const label = routeLabelText[route.label];
  const extra = formatExtra(route.extra_minutes);
  const diff = formatDiff(route.exposure_diff_vs_fastest);
  const fewer = route.exposure_diff_vs_fastest != null && route.exposure_diff_vs_fastest.p50 < 0;
  const minutes = formatMinutes(route.minutes);
  const style = { "--route": ROUTE_COLORS[route.label], animationDelay: `${index * 70}ms` } as CSSProperties;
  const classes = ["route-card", selected ? "selected" : "", recommended ? "recommended" : ""].filter(Boolean).join(" ");

  return (
    <article className={classes} style={style}>
      <button
        type="button"
        className="route-select"
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={strings.routeSummary(label, minutes)}
      >
        <span className="route-head">
          <span className="route-swatch" aria-hidden="true">
            {selected ? <CheckIcon size={12} /> : null}
          </span>
          <span className="route-name">{label}</span>
          {recommended ? <span className="route-badge">{strings.recommendedBadge}</span> : null}
        </span>
        <span className="route-time">
          <strong>{minutes}</strong>
          <small>
            {extra ? <span className="route-extra">{extra}</span> : null}
            {formatDistance(route.distance_m)}
          </small>
        </span>
      </button>

      <div className="route-stats">
        <div className="stat">
          <span className="stat-value">≈ {formatCount(route.exposure.p50)}</span>
          <span className="stat-label" title={units}>{exposureNoun}</span>
          <span className="stat-range">
            {strings.likelyRange(formatCount(route.exposure.p10), formatCount(route.exposure.p90))}
          </span>
        </div>
        {diff ? (
          <div className={fewer ? "stat stat-diff fewer" : "stat stat-diff"}>
            <span className="diff-chip">
              {fewer ? <ArrowDownIcon /> : <EqualIcon />}
              {strings.vsFastest}
            </span>
            <span className="diff">{diff}</span>
          </div>
        ) : null}
      </div>

      {route.draws_better != null ? <StabilityBadge drawsBetter={route.draws_better} nDraws={nDraws} /> : null}
      <div className="card-actions">
        <button type="button" className="btn-quiet btn-segments" aria-pressed={segmentsOpen} onClick={onShowSegments}>
          <SegmentsIcon />
          {strings.showSegments}
        </button>
      </div>
      {selected ? (
        <button type="button" className="btn-primary btn-start" onClick={onStartWalk}>
          <PlayIcon />
          {startLabel}
        </button>
      ) : null}
    </article>
  );
}
