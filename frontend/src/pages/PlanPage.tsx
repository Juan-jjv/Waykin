import { useEffect, useRef, useState } from "react";
import { ApiError, TraceError } from "../api/client";
import { insideBBox, type Place } from "../api/geocode";
import { useIncidents, useMeta, usePlanRoutes } from "../api/hooks";
import type { DemoPreset, LatLon, RouteOption } from "../api/types";
import { IncidentLayer } from "../components/IncidentLayer";
import { MapFilters } from "../components/MapFilters";
import { MapView } from "../components/MapView";
import { PointMarkers, PointSearch } from "../components/PointPicker";
import { PresetPicker } from "../components/PresetPicker";
import { FitRoutes, RouteLayer, SegmentFocus } from "../components/RouteLayer";
import { RoutePanel, RouteSkeleton } from "../components/RoutePanel";
import { strings } from "../copy/strings";

const DRAFT_KEY = "waykin:route:draft";

export function PlanPage() {
  const metaQuery = useMeta();
  const meta = metaQuery.data;
  const [origin, setOrigin] = useState<LatLon | null>(null);
  const [destination, setDestination] = useState<LatLon | null>(null);
  const [originLabel, setOriginLabel] = useState<string | null>(null);
  const [destinationLabel, setDestinationLabel] = useState<string | null>(null);
  const [categories, setCategories] = useState<string[] | null>(null);
  const [incidentsOn, setIncidentsOn] = useState(true);
  const [days, setDays] = useState(30);
  const [presetId, setPresetId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [routeToken, setRouteToken] = useState(0);
  const [focus, setFocus] = useState<{ token: number; geometry: number[][] } | null>(null);
  const [segmentRouteId, setSegmentRouteId] = useState<string | null>(null);
  const [walkNote, setWalkNote] = useState<string | null>(null);
  const plan = usePlanRoutes();
  const touchedOrigin = useRef(false);

  const radius = meta?.default_radius_m ?? 100;
  const activeCategories = categories ?? meta?.categories ?? [];
  const showIncidents = incidentsOn && activeCategories.length > 0;
  const incidents = useIncidents(radius, activeCategories, days, Boolean(meta) && showIncidents);
  const windowLabel = strings.dateWindows.find((window) => window.days === days)?.label ?? "";

  const bbox = meta?.bbox;
  useEffect(() => {
    if (!bbox || !("geolocation" in navigator)) return;
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const here = { lat: position.coords.latitude, lon: position.coords.longitude };
        if (touchedOrigin.current || !insideBBox(here, bbox)) return;
        setOrigin(here);
        setOriginLabel(strings.yourLocation);
        setFocus({ token: Date.now(), geometry: [[here.lat, here.lon]] });
      },
      () => undefined,
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  }, [bbox]);

  function clearPlan() {
    plan.reset();
    setSelectedId(null);
    setFocus(null);
    setSegmentRouteId(null);
    setWalkNote(null);
    setRouteToken(0);
  }

  function focusOn(points: (LatLon | null)[]) {
    const geometry = points.filter((p): p is LatLon => p !== null).map((p) => [p.lat, p.lon]);
    if (geometry.length > 0) setFocus({ token: Date.now(), geometry });
  }

  function updateOrigin(point: LatLon, label: string) {
    touchedOrigin.current = true;
    setPresetId(null);
    setOrigin(point);
    setOriginLabel(label);
    clearPlan();
    focusOn([point, destination]);
  }

  function updateDestination(point: LatLon, label: string) {
    setPresetId(null);
    setDestination(point);
    setDestinationLabel(label);
    clearPlan();
    focusOn([origin, point]);
  }

  function applyPreset(preset: DemoPreset) {
    touchedOrigin.current = true;
    setPresetId(preset.id);
    setOrigin(preset.origin);
    setDestination(preset.destination);
    setOriginLabel(strings.presetStart(preset.name));
    setDestinationLabel(strings.presetEnd(preset.name));
    clearPlan();
    focusOn([preset.origin, preset.destination]);
  }

  function swapPoints() {
    if (!origin || !destination) return;
    setPresetId(null);
    setOrigin(destination);
    setDestination(origin);
    setOriginLabel(destinationLabel);
    setDestinationLabel(originLabel);
    clearPlan();
  }

  function clearPoints() {
    touchedOrigin.current = true;
    setPresetId(null);
    setOrigin(null);
    setDestination(null);
    setOriginLabel(null);
    setDestinationLabel(null);
    clearPlan();
  }

  function changeCategories(next: string[]) {
    setCategories(next);
    setIncidentsOn(next.length > 0);
  }

  function toggleIncidents(next: boolean) {
    if (next && activeCategories.length === 0 && meta) setCategories(meta.categories);
    setIncidentsOn(next);
  }

  function findRoutes() {
    if (!origin || !destination) return;
    setWalkNote(null);
    setFocus(null);
    setSegmentRouteId(null);
    plan.mutate(
      { origin, destination },
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
        <MapView bbox={meta.bbox} showBBox={outside}>
          {showIncidents && incidents.data ? (
            <IncidentLayer points={incidents.data.points} windowLabel={windowLabel} />
          ) : null}
          {plan.isSuccess && plan.data ? (
            <>
              <RouteLayer routes={plan.data.routes} selectedId={selectedId} onSelect={setSelectedId} />
              <FitRoutes token={routeToken} routes={plan.data.routes} />
            </>
          ) : null}
          <SegmentFocus focus={focus} />
          <PointMarkers
            origin={origin}
            destination={destination}
            onOrigin={(point) => updateOrigin(point, strings.droppedPin)}
            onDestination={(point) => updateDestination(point, strings.droppedPin)}
          />
        </MapView>
        <MapFilters
          incidentsOn={showIncidents}
          onIncidents={toggleIncidents}
          days={days}
          onDays={setDays}
          categories={meta.categories}
          selected={activeCategories}
          onCategories={changeCategories}
          asOf={meta.provenance.as_of}
        />
      </div>
      <aside className="sheet">
        <header className="sheet-head">
          <h1>{strings.appName}</h1>
          <p className="tagline">{strings.tagline}</p>
        </header>
        {meta.demo_mode ? (
          <PresetPicker presets={meta.demo_presets} selectedId={presetId} onSelect={applyPreset} />
        ) : null}
        <PointSearch
          originLabel={originLabel}
          destinationLabel={destinationLabel}
          bbox={meta.bbox}
          canSwap={ready}
          canClear={Boolean(origin || destination)}
          onOrigin={(place: Place) => updateOrigin(place.point, place.label)}
          onDestination={(place: Place) => updateDestination(place.point, place.label)}
          onSwap={swapPoints}
          onClear={clearPoints}
        />
        <button type="button" className="btn-primary find" onClick={findRoutes} disabled={!ready || plan.isPending}>
          {plan.isPending ? strings.finding : strings.findRoutes}
        </button>
        {showHint ? <p className="hint">{ready ? strings.findHint : strings.searchHint}</p> : null}
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
