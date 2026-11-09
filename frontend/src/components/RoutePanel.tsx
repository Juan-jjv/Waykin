import type { RouteOption, RoutesResponse, TravelMode } from "../api/types";
import { routeLabelText, strings } from "../copy/strings";
import { AbstainCard } from "./AbstainCard";
import { SparkIcon } from "./icons";
import { RouteCard } from "./RouteCard";

export function RoutePanel({
  response,
  selectedId,
  segmentRouteId,
  onSelect,
  onShowSegments,
  onStartWalk,
  walkNote,
  mode = "walk",
}: {
  response: RoutesResponse;
  selectedId: string | null;
  segmentRouteId: string | null;
  onSelect: (routeId: string) => void;
  onShowSegments: (route: RouteOption) => void;
  onStartWalk: (route: RouteOption) => void;
  walkNote: string | null;
  mode?: TravelMode;
}) {
  const { decision } = response;
  const recommended = response.routes.find((route) => route.route_id === decision.recommended_route_id);

  return (
    <div className="route-panel">
      {decision.status === "recommend" && recommended ? (
        <header className="decision">
          <span className="decision-icon" aria-hidden="true">
            <SparkIcon />
          </span>
          <div>
            <h2 className="decision-title">{strings.recommended(routeLabelText[recommended.label])}</h2>
            <p>{decision.message}</p>
          </div>
        </header>
      ) : null}
      {decision.status === "abstain" && decision.reason ? <AbstainCard reason={decision.reason} maxExtra={decision.thresholds.max_extra_time} /> : null}
      {response.routes.map((route, index) => (
        <RouteCard
          key={route.route_id}
          index={index}
          route={route}
          units={response.provenance.units}
          nDraws={decision.n_draws}
          selected={route.route_id === selectedId}
          recommended={route.route_id === decision.recommended_route_id}
          segmentsOpen={route.route_id === segmentRouteId}
          onSelect={() => onSelect(route.route_id)}
          onShowSegments={() => onShowSegments(route)}
          onStartWalk={() => onStartWalk(route)}
          startLabel={mode === "drive" ? strings.startDrive : strings.startWalk}
          exposureNoun={mode === "walk" ? strings.walkExposureNoun : undefined}
        />
      ))}
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
      <span className="sk sk-line" />
      <span className="sk sk-card" />
      <span className="sk sk-card" />
    </div>
  );
}
