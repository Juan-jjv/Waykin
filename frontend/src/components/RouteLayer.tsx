import { useEffect, useRef } from "react";
import type { MapLayerMouseEvent, Map as MapLibreMap } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { RouteOption } from "../api/tmp-types";
import { useWaykinMap } from "../map/context";
import { fitPadding } from "../map/fitPadding";
import { removeMapSource, setGeoJson, toLngLatLine, whenStyleReady } from "../map/geojson";
import { ROUTE_COLORS, SEGMENT_COLOR } from "../map/colors";
import { useAppearance } from "../theme/appearance";

const SOURCE = "waykin-routes";
const SEGMENT_SOURCE = "waykin-segments";
const ROUTE_LAYERS = ["waykin-route-casing", "waykin-route-line", "waykin-route-hit"];
const SEGMENT_LAYERS = ["waykin-segment-casing", "waykin-segment-line"];

export function RouteLayer({
  routes,
  selectedId,
  onSelect,
}: {
  routes: RouteOption[];
  selectedId: string | null;
  onSelect: (routeId: string) => void;
}) {
  const map = useWaykinMap();
  const { appearance } = useAppearance();
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const casing = appearance === "dark" ? "rgba(248,250,252,0.92)" : "#ffffff";

  useEffect(() => {
    const onClick = (event: MapLayerMouseEvent) => {
      const routeId = event.features?.[0]?.properties?.route_id;
      if (typeof routeId === "string") onSelectRef.current(routeId);
    };
    const onEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = "";
    };

    const apply = () => {
      const data: FeatureCollection = {
        type: "FeatureCollection",
        features: routes.map((route) => ({
          type: "Feature",
          properties: {
            route_id: route.route_id,
            color: ROUTE_COLORS[route.label],
            casing,
            selected: route.route_id === selectedId ? 1 : 0,
          },
          geometry: { type: "LineString", coordinates: toLngLatLine(route.geometry) },
        })),
      };
      setGeoJson(map, SOURCE, data);
      if (!map.getLayer(ROUTE_LAYERS[0])) {
        map.addLayer({
          id: ROUTE_LAYERS[0],
          type: "line",
          source: SOURCE,
          layout: { "line-cap": "round", "line-join": "round", "line-sort-key": ["get", "selected"] },
          paint: {
            "line-color": ["get", "casing"],
            "line-width": ["interpolate", ["linear"], ["get", "selected"], 0, 8, 1, 12],
            "line-opacity": 0.95,
          },
        });
      }
      if (!map.getLayer(ROUTE_LAYERS[1])) {
        map.addLayer({
          id: ROUTE_LAYERS[1],
          type: "line",
          source: SOURCE,
          layout: { "line-cap": "round", "line-join": "round", "line-sort-key": ["get", "selected"] },
          paint: {
            "line-color": ["get", "color"],
            "line-width": ["interpolate", ["linear"], ["get", "selected"], 0, 4, 1, 7],
            "line-opacity": ["interpolate", ["linear"], ["get", "selected"], 0, 0.78, 1, 1],
          },
        });
      }
      if (!map.getLayer(ROUTE_LAYERS[2])) {
        map.addLayer({
          id: ROUTE_LAYERS[2],
          type: "line",
          source: SOURCE,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: {
            "line-color": ["get", "color"],
            "line-width": 18,
            "line-opacity": 0.01,
          },
        });
      }
      map.off("click", ROUTE_LAYERS[2], onClick);
      map.off("mouseenter", ROUTE_LAYERS[2], onEnter);
      map.off("mouseleave", ROUTE_LAYERS[2], onLeave);
      map.on("click", ROUTE_LAYERS[2], onClick);
      map.on("mouseenter", ROUTE_LAYERS[2], onEnter);
      map.on("mouseleave", ROUTE_LAYERS[2], onLeave);

      const selected = routes.find((route) => route.route_id === selectedId);
      const segments = selected?.top_segments ?? [];
      const segmentData: FeatureCollection = {
        type: "FeatureCollection",
        features: segments
          .filter((segment) => segment.geometry.length >= 2)
          .map((segment) => ({
            type: "Feature",
            properties: { color: selected ? ROUTE_COLORS[selected.label] : SEGMENT_COLOR },
            geometry: { type: "LineString", coordinates: toLngLatLine(segment.geometry) },
          })),
      };
      setGeoJson(map, SEGMENT_SOURCE, segmentData);
      if (!map.getLayer(SEGMENT_LAYERS[0])) {
        map.addLayer({
          id: SEGMENT_LAYERS[0],
          type: "line",
          source: SEGMENT_SOURCE,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": SEGMENT_COLOR, "line-width": 12, "line-opacity": 0.95 },
        });
      }
      if (!map.getLayer(SEGMENT_LAYERS[1])) {
        map.addLayer({
          id: SEGMENT_LAYERS[1],
          type: "line",
          source: SEGMENT_SOURCE,
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": ["get", "color"], "line-width": 6, "line-opacity": 1 },
        });
      }
    };

    const stop = whenStyleReady(map, apply);
    return () => {
      stop();
      map.off("click", ROUTE_LAYERS[2], onClick);
      map.off("mouseenter", ROUTE_LAYERS[2], onEnter);
      map.off("mouseleave", ROUTE_LAYERS[2], onLeave);
      if (map.getStyle()) {
        removeMapSource(map, SOURCE, ROUTE_LAYERS);
        removeMapSource(map, SEGMENT_SOURCE, SEGMENT_LAYERS);
      }
    };
  }, [map, routes, selectedId, casing]);

  return null;
}

export function FitRoutes({ token, routes }: { token: number; routes: RouteOption[] }) {
  const map = useWaykinMap();

  useEffect(() => {
    if (token === 0 || routes.length === 0) return;
    const points = routes.flatMap((route) => route.geometry);
    fitLatLon(map, points, 16);
  }, [token, map, routes]);

  return null;
}

export function SegmentFocus({
  focus,
}: {
  focus: { token: number; geometry: [number, number][] } | null;
}) {
  const map = useWaykinMap();

  useEffect(() => {
    if (!focus || focus.geometry.length === 0) return;
    fitLatLon(map, focus.geometry, 17);
  }, [focus, map]);

  return null;
}

function fitLatLon(map: MapLibreMap, points: [number, number][], maxZoom: number): void {
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const [lat, lon] of points) {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  if (!Number.isFinite(west)) return;
  map.fitBounds(
    [
      [west, south],
      [east, north],
    ],
    { padding: fitPadding(), maxZoom, duration: 700 },
  );
}
