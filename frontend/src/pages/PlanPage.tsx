import { useState } from "react";
import { ApiError } from "../api/client";
import { useMeta, usePlanRoutes } from "../api/hooks";
import type { LatLon, RoutesResponse } from "../api/types";
import { MapView } from "../components/MapView";
import { PointPicker } from "../components/PointPicker";
import { RouteLayer } from "../components/RouteLayer";
import { RoutePanel } from "../components/RoutePanel";
import { STR } from "../copy/strings";

function defaultSelection(data: RoutesResponse): string | null {
  return data.decision.recommended_route_id ?? data.routes[0]?.route_id ?? null;
}

export function PlanPage() {
  const meta = useMeta();
  const plan = usePlanRoutes();
  const [origin, setOrigin] = useState<LatLon | null>(null);
  const [destination, setDestination] = useState<LatLon | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  if (meta.isLoading) return <div className="center">Loading…</div>;
  if (meta.isError || !meta.data) {
    return (
      <div className="center">
        <p>{STR.serverDown}</p>
        <button onClick={() => meta.refetch()}>{STR.retry}</button>
      </div>
    );
  }

  const m = meta.data;
  const err = plan.error instanceof ApiError ? plan.error : null;
  const setPoints = (o: LatLon | null, d: LatLon | null) => {
    setOrigin(o);
    setDestination(d);
    plan.reset();
  };
  const find = () => {
    if (!origin || !destination) return;
    plan.mutate(
      { origin, destination, radius_m: m.default_radius_m as 50 | 100 | 200 },
      { onSuccess: (d) => setSelected(defaultSelection(d)) },
    );
  };

  return (
    <div className="layout">
      <header className="topbar">
        <strong>{STR.appName}</strong>
        <span className="muted">{STR.tagline}</span>
      </header>
      <MapView provenance={plan.data?.provenance ?? m.provenance} bbox={m.bbox} showBbox={err?.code === "outside_area"}>
        <PointPicker origin={origin} destination={destination} onChange={setPoints} />
        {plan.data && <RouteLayer routes={plan.data.routes} selectedId={selected} onSelect={setSelected} />}
      </MapView>
      <aside className="side">
        <div className="controls">
          <p className="muted">{!origin ? STR.pickOrigin : !destination ? STR.pickDestination : " "}</p>
          <div className="row">
            <button className="primary" disabled={!origin || !destination || plan.isPending} onClick={find}>
              {plan.isPending ? STR.finding : STR.findRoutes}
            </button>
            <button disabled={!origin || !destination} onClick={() => setPoints(destination, origin)}>{STR.swap}</button>
            <button disabled={!origin} onClick={() => setPoints(null, null)}>{STR.clear}</button>
          </div>
          {err && <p className="error">{err.code === "outside_area" ? STR.outsideArea : err.code === "no_path" ? STR.noPath : err.message}</p>}
        </div>
        {plan.isPending && <div className="panel skeleton" aria-busy="true" />}
        {plan.data && <RoutePanel data={plan.data} selectedId={selected} onSelect={setSelected} />}
      </aside>
    </div>
  );
}
