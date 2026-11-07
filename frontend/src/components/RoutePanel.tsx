import type { RoutesResponse } from "../api/types";
import { ABSTAIN, LABELS, STR } from "../copy/strings";
import { ROUTE_COLORS } from "./RouteLayer";

/** Decision summary, then one card per route. Abstaining is a first-class result, not an error. */
export function RoutePanel({ data, selectedId, onSelect }: {
  data: RoutesResponse;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const { decision } = data;
  const rec = data.routes.find((r) => r.route_id === decision.recommended_route_id);
  return (
    <section className="panel" aria-label="Route comparison">
      {decision.status === "recommend" && rec ? (
        <div className="decision recommend">
          <h2>{STR.recommended(LABELS[rec.label])}</h2>
          <p>{decision.message}</p>
        </div>
      ) : (
        decision.reason && (
          <div className="decision abstain" data-testid="abstain-card">
            <h2>{ABSTAIN[decision.reason].headline}</h2>
            <p>{ABSTAIN[decision.reason].body}</p>
            <details>
              <summary>{STR.whyAbstainTitle}</summary>
              <p className="muted">{STR.whyAbstain}</p>
            </details>
          </div>
        )
      )}
      {data.routes.map((r) => (
        <button
          key={r.route_id}
          className={`route-card ${r.route_id === selectedId ? "selected" : ""}`}
          onClick={() => onSelect(r.route_id)}
          aria-pressed={r.route_id === selectedId}
        >
          <div className="route-head">
            <span className="swatch" style={{ background: ROUTE_COLORS[r.label] }} />
            <strong>{LABELS[r.label]}</strong>
            {r.route_id === decision.recommended_route_id && <span className="pill">Recommended</span>}
            <span className="spacer" />
            <span>{STR.minutes(r.minutes)}</span>
            {r.label !== "fastest" && <span className="muted">{STR.extra(r.extra_minutes)}</span>}
          </div>
          <div>{STR.exposure(r.exposure.p50, r.exposure.p10, r.exposure.p90)}</div>
          {r.exposure_diff_vs_fastest && (
            <div className="muted">
              {STR.fewer(r.exposure_diff_vs_fastest.p50, r.exposure_diff_vs_fastest.p10, r.exposure_diff_vs_fastest.p90)}
            </div>
          )}
          {r.draws_better !== null && r.draws_better !== undefined && (
            <div className="stability">{STR.holds(r.draws_better, decision.n_draws)}</div>
          )}
          <div className="muted small">{r.explanation}</div>
        </button>
      ))}
      <p className="muted small">{data.provenance.units}</p>
    </section>
  );
}
