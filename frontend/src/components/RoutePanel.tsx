import type { RouteOption, RoutesResponse } from "../api/tmp-types";
import { routeLabelText, strings } from "../copy/strings";
import { AbstainCard } from "./AbstainCard";
import { RadiusBadge } from "./RadiusBadge";
import { RouteCard } from "./RouteCard";

export function RoutePanel({
  response,
  selectedId,
  segmentRouteId,
  onSelect,
  onShowSegments,
  onStartWalk,
  walkNote,
}: {
  response: RoutesResponse;
  selectedId: string | null;
  segmentRouteId: string | null;
  onSelect: (routeId: string) => void;
  onShowSegments: (route: RouteOption) => void;
  onStartWalk: (route: RouteOption) => void;
  walkNote: string | null;
}) {
  const { decision } = response;
  const recommended = response.routes.find((route) => route.route_id === decision.recommended_route_id);

  return (
    <div className="route-panel">
      {decision.status === "recommend" && recommended ? (
        <header className="decision">
          <h2 className="decision-title">{strings.recommended(routeLabelText[recommended.label])}</h2>
          <p>{decision.message}</p>
        </header>
      ) : null}
      {decision.status === "abstain" && decision.reason ? <AbstainCard reason={decision.reason} /> : null}
      {response.routes.map((route) => (
        <RouteCard
          key={route.route_id}
          route={route}
          units={response.provenance.units}
          nDraws={decision.n_draws}
          selected={route.route_id === selectedId}
          segmentsOpen={route.route_id === segmentRouteId}
          onSelect={() => onSelect(route.route_id)}
          onShowSegments={() => onShowSegments(route)}
          onStartWalk={() => onStartWalk(route)}
        />
      ))}
      {decision.radius_sensitive ? <RadiusBadge decisions={decision.radius_decisions} /> : null}
      {walkNote ? (
        <p className="walk-note" role="status">
          {walkNote}
        </p>
      ) : null}
    </div>
  );
}

export function RouteSkeleton() {
  return (
    <div className="skeleton" role="status" aria-label={strings.finding}>
      <span className="sk sk-title" />
      <span className="sk sk-card" />
      <span className="sk sk-card" />
      <span className="sk sk-card" />
    </div>
  );
}
