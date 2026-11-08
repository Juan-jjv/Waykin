import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { ApiError, TraceError } from "../api/client";
import { insideBBox, type Place } from "../api/geocode";
import { useIncidents, useMeta, usePlanRoutes } from "../api/hooks";
import type { DemoPreset, LatLon, RouteOption, TravelMode } from "../api/types";
import { IncidentLayer } from "../components/IncidentLayer";
import { MapLegend } from "../components/MapLegend";
import { MapFilters } from "../components/MapFilters";
import { MapView } from "../components/MapView";
import { ModePicker } from "../components/ModePicker";
import { PeoplePins } from "../components/PeoplePins";
import { PointMarkers, PointSearch } from "../components/PointPicker";
import type { QuickPlace } from "../components/PlaceSearch";
import { PresetPicker } from "../components/PresetPicker";
import { FitRoutes, RouteLayer, SegmentFocus } from "../components/RouteLayer";
import { RoutePanel, RouteSkeleton } from "../components/RoutePanel";
import { strings } from "../copy/strings";
import { useAccount, useDemoPeople } from "../family/api";

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
  const [mode, setMode] = useState<TravelMode>("walk");
  const plan = usePlanRoutes();
  const touchedOrigin = useRef(false);
  const navigate = useNavigate();

  const radius = meta?.default_radius_m ?? 100;
  const activeCategories = categories ?? meta?.categories ?? [];
  const showIncidents = incidentsOn && activeCategories.length > 0;
  const incidents = useIncidents(radius, activeCategories, days, Boolean(meta) && showIncidents);
  const windowLabel = strings.dateWindows.find((window) => window.days === days)?.label ?? "";

  const me = useAccount().data ?? null;
  const demoPeople = useDemoPeople(meta?.demo_mode ? (me?.account_id ?? null) : null);
  const people = useMemo(() => (me ? demoPeople.data?.people ?? [] : []), [me, demoPeople.data]);

  const bbox = meta?.bbox;
  // Ready-made choices for both the Start and End fields: this device's location, then the family members.
  const placeChoices = useMemo<QuickPlace[]>(() => {
    const here: QuickPlace = {
      key: "here",
      label: strings.yourLocation,
      hint: strings.yourLocationHint,
      pick: () => locate(bbox ?? []),
    };
    const family = people.map((person) => ({
      key: `person-${person.account_id}`,
      label: person.display_name,
      hint: person.near ? strings.personNear(person.near) : undefined,
      pick: () => ({ label: person.display_name, point: person.position }),
    }));
    return [here, ...family];
  }, [bbox, people]);

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

  function changeMode(next: TravelMode) {
    if (next === mode) return;
    setMode(next);
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
      { origin, destination, mode },
      {
        onSuccess: (data) => {
          setSelectedId(data.decision.recommended_route_id ?? defaultRouteId(data.routes, data.mode));
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
      sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ route, destination, originLabel, destinationLabel, mode }));
      navigate("/walk");
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
            <>
              <IncidentLayer points={incidents.data.points} windowLabel={windowLabel} severity={meta.severity ?? {}} />
              <MapLegend />
            </>
          ) : null}
          {plan.isSuccess && plan.data ? (
            <>
              <RouteLayer routes={plan.data.routes} selectedId={selectedId} onSelect={setSelectedId} />
              <FitRoutes token={routeToken} routes={plan.data.routes} />
            </>
          ) : null}
          <SegmentFocus focus={focus} />
          <PeoplePins people={people} onStart={updateOrigin} onEnd={updateDestination} />
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
          <NavBar />
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
          startChoices={placeChoices}
          endChoices={placeChoices}
        />
        <ModePicker modes={meta.modes} mode={mode} onChange={changeMode} />
        <button type="button" className="btn-primary find" onClick={findRoutes} disabled={!ready || plan.isPending}>
          {plan.isPending ? strings.finding : strings.findRoutes}
        </button>
        {showHint ? <p className="hint">{ready ? strings.findHint : strings.searchHint}</p> : null}
        {plan.isPending ? <RouteSkeleton /> : null}
        {plan.isError ? <p className="notice">{routeErrorCopy(plan.error, mode)}</p> : null}
        {plan.isSuccess && plan.data ? (
          <RoutePanel
            response={plan.data}
            selectedId={selectedId}
            segmentRouteId={segmentRouteId}
            onSelect={setSelectedId}
            onShowSegments={showSegments}
            onStartWalk={startWalk}
            walkNote={walkNote}
            mode={plan.data.mode}
          />
        ) : null}
      </aside>
    </div>
  );
}

/** The device's position as a start, if the browser shares it and it's inside the map area. */
function locate(bbox: number[]): Promise<Place> {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject(new Error(strings.locationUnavailable));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const point = { lat: position.coords.latitude, lon: position.coords.longitude };
        if (bbox.length === 4 && !insideBBox(point, bbox)) reject(new Error(strings.locationOutside));
        else resolve({ label: strings.yourLocation, point });
      },
      () => reject(new Error(strings.locationDenied)),
      { enableHighAccuracy: true, timeout: 10_000, maximumAge: 60_000 },
    );
  });
}

/** Without a recommendation: on foot, start from the option passing the fewest reports; by car, the fastest. */
function defaultRouteId(routes: RouteOption[], mode: TravelMode): string | null {
  if (routes.length === 0) return null;
  if (mode === "walk") {
    return routes.reduce((best, route) => (route.exposure.p50 < best.exposure.p50 ? route : best)).route_id;
  }
  return (routes.find((route) => route.label === "fastest") ?? routes[0]).route_id;
}

function routeErrorCopy(error: unknown, mode: TravelMode): string {
  if (error instanceof TraceError) return strings.streetsUnavailable;
  if (error instanceof ApiError) {
    if (error.code === "outside_area") return strings.outsideArea;
    if (error.code === "no_path") return strings.noPath(mode);
  }
  return strings.cantReach;
}
