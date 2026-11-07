import { useState } from "react";
import { ApiError, TraceError } from "../api/client";
import { useIncidents, useMeta, usePlanRoutes } from "../api/hooks";
import type { DemoPreset, LatLon, RadiusM, RouteOption } from "../api/tmp-types";
import { CategoryFilter } from "../components/CategoryFilter";
import { IncidentLayer, IncidentToggle } from "../components/IncidentLayer";
import { MapView } from "../components/MapView";
import { PointMarkers, PointSummary } from "../components/PointPicker";
import { PresetPicker } from "../components/PresetPicker";
import { RadiusSelect } from "../components/RadiusSelect";
import { FitRoutes, RouteLayer, SegmentFocus } from "../components/RouteLayer";
import { RoutePanel, RouteSkeleton } from "../components/RoutePanel";
import { strings } from "../copy/strings";

const DRAFT_KEY = "waykin:route:draft";

export function PlanPage() {
  const metaQuery = useMeta();
  const meta = metaQuery.data;
  const [origin, setOrigin] = useState<LatLon | null>(null);
  const [destination, setDestination] = useState<LatLon | null>(null);
  const [radius, setRadius] = useState<RadiusM | null>(null);
  const [categories, setCategories] = useState<string[] | null>(null);
  const [incidentsOn, setIncidentsOn] = useState(true);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [routeToken, setRouteToken] = useState(0);
  const [focus, setFocus] = useState<{ token: number; geometry: [number, number][] } | null>(null);
  const [segmentRouteId, setSegmentRouteId] = useState<string | null>(null);
  const [walkNote, setWalkNote] = useState<string | null>(null);
  const plan = usePlanRoutes();

  const activeRadius: RadiusM = radius ?? meta?.default_radius_m ?? 100;
  const activeCategories = categories ?? meta?.categories ?? [];
  const incidents = useIncidents(activeRadius, activeCategories, Boolean(meta) && incidentsOn);

  function clearPlan() {
    plan.reset();
    setSelectedId(null);
    setFocus(null);
    setSegmentRouteId(null);
    setWalkNote(null);
    setRouteToken(0);
  }

  function updateOrigin(point: LatLon) {
    setPresetId(null);
    setOrigin(point);
    clearPlan();
  }

  function updateDestination(point: LatLon) {
    setPresetId(null);
    setDestination(point);
    clearPlan();
  }

  function applyPreset(preset: DemoPreset) {
    setPresetId(preset.id);
    setOrigin(preset.origin);
    setDestination(preset.destination);
    clearPlan();
  }

  function swapPoints() {
    if (!origin || !destination) return;
    setPresetId(null);
    setOrigin(destination);
    setDestination(origin);
    clearPlan();
  }

  function clearPoints() {
    setPresetId(null);
    setOrigin(null);
    setDestination(null);
    clearPlan();
  }

  function findRoutes() {
    if (!origin || !destination) return;
    setWalkNote(null);
    setFocus(null);
    setSegmentRouteId(null);
    plan.mutate(
      { origin, destination, radius_m: activeRadius },
      {
        onSuccess: (data) => {
          const fastest = data.routes.find((route) => route.label === "fastest");
          setSelectedId(data.decision.recommended_route_id ?? fastest?.route_id ?? null);
          setRouteToken((value) => value + 1);
        },
      },
    );
  }

  function showSegments(route: RouteOption) {
    setSelectedId(route.route_id);
    setSegmentRouteId(route.route_id);
    setFocus({
      token: Date.now(),
      geometry: route.top_segments.flatMap((segment) => segment.geometry),
    });
  }

  function startWalk(route: RouteOption) {
    if (!destination) return;
    try {
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ route, destination }));
      setWalkNote(strings.walkSaved);
    } catch {
      setWalkNote(strings.walkSaveFailed);
    }
  }

  if (metaQuery.isError) {
    return (
      <div className="fatal">
        <div className="fatal-card">
          <h1>{strings.cantReach}</h1>
          <button type="button" className="btn-primary" onClick={() => void metaQuery.refetch()}>
            {strings.retry}
          </button>
        </div>
      </div>
    );
  }

  if (!meta) {
    return (
      <div className="fatal">
        <p>{strings.opening}</p>
      </div>
    );
  }

  const outside = plan.isError && plan.error instanceof ApiError && plan.error.code === "outside_area";
  const ready = Boolean(origin && destination);
  const showHint = !plan.isPending && !plan.isSuccess && !plan.isError;

  return (
    <div className="app-shell">
      <div className="map-stage">
        <MapView bbox={meta.bbox} showBBox={outside} picking={!origin || !destination}>
          {incidentsOn && incidents.data ? <IncidentLayer points={incidents.data.points} /> : null}
          {plan.isSuccess && plan.data ? (
            <>
              <RouteLayer routes={plan.data.routes} selectedId={selectedId} onSelect={setSelectedId} />
              <FitRoutes token={routeToken} routes={plan.data.routes} />
              <SegmentFocus focus={focus} />
            </>
          ) : null}
          <PointMarkers
            origin={origin}
            destination={destination}
            onOrigin={updateOrigin}
            onDestination={updateDestination}
          />
        </MapView>
      </div>
      <aside className="sheet">
        <header className="sheet-head">
          <h1>{strings.appName}</h1>
          <p className="tagline">{strings.tagline}</p>
        </header>
        {meta.demo_mode ? (
          <PresetPicker presets={meta.demo_presets} selectedId={presetId} onSelect={applyPreset} />
        ) : null}
        <PointSummary origin={origin} destination={destination} onSwap={swapPoints} onClear={clearPoints} />
        <RadiusSelect
          radii={meta.radii}
          value={activeRadius}
          onChange={(next) => {
            setRadius(next);
            clearPlan();
          }}
        />
        <section className="incident-controls">
          <IncidentToggle on={incidentsOn} onChange={setIncidentsOn} />
          <CategoryFilter categories={meta.categories} selected={activeCategories} onChange={setCategories} />
        </section>
        <button type="button" className="btn-primary find" onClick={findRoutes} disabled={!ready || plan.isPending}>
          {plan.isPending ? strings.finding : strings.findRoutes}
        </button>
        {showHint ? <p className="hint">{ready ? strings.findHint : strings.tapHint}</p> : null}
        {plan.isPending ? <RouteSkeleton /> : null}
        {plan.isError ? <p className="notice">{routeErrorCopy(plan.error)}</p> : null}
        {plan.isSuccess && plan.data ? (
          <RoutePanel
            response={plan.data}
            selectedId={selectedId}
            segmentRouteId={segmentRouteId}
            onSelect={setSelectedId}
            onShowSegments={showSegments}
            onStartWalk={startWalk}
            walkNote={walkNote}
          />
        ) : null}
      </aside>
    </div>
  );
}

function routeErrorCopy(error: unknown): string {
  if (error instanceof TraceError) return strings.streetsUnavailable;
  if (error instanceof ApiError) {
    if (error.code === "outside_area") return strings.outsideArea;
    if (error.code === "no_path") return strings.noPath;
  }
  return strings.cantReach;
}
