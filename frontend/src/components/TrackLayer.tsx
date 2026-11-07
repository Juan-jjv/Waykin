import { useEffect, useRef } from "react";
import type { FeatureCollection } from "geojson";
import { useWaykinMap } from "../map/context";
import { removeMapSource, setGeoJson, toLngLatLine, whenStyleReady } from "../map/geojson";

const SOURCE = "waykin-track";
const LAYERS = ["waykin-track-closure", "waykin-track-casing", "waykin-track-line", "waykin-track-me-halo", "waykin-track-me"];

export type Closure = { lat: number; lon: number; radius_m: number };

/** A live walk on the map: the route, closures, and the walker's position (followed unless the user pans away). */
export function TrackLayer({
  route,
  position,
  closures = [],
  color = "#2563eb",
}: {
  route: number[][] | null;
  position: { lat: number; lon: number } | null;
  closures?: Closure[];
  color?: string;
}) {
  const map = useWaykinMap();
  const follow = useRef(true);

  useEffect(() => {
    const stop = () => {
      follow.current = false;
    };
    map.on("dragstart", stop);
    return () => {
      map.off("dragstart", stop);
    };
  }, [map]);

  useEffect(() => {
    const apply = () => {
      const features: FeatureCollection["features"] = [];
      for (const c of closures) {
        features.push({ type: "Feature", properties: { kind: "closure", r: c.radius_m }, geometry: { type: "Point", coordinates: [c.lon, c.lat] } });
      }
      if (route && route.length >= 2) {
        features.push({ type: "Feature", properties: { kind: "route" }, geometry: { type: "LineString", coordinates: toLngLatLine(route) } });
      }
      if (position) {
        features.push({ type: "Feature", properties: { kind: "me" }, geometry: { type: "Point", coordinates: [position.lon, position.lat] } });
      }
      setGeoJson(map, SOURCE, { type: "FeatureCollection", features });
      const add = (id: string, spec: Record<string, unknown>) => {
        if (!map.getLayer(id)) map.addLayer({ id, source: SOURCE, ...spec } as never);
      };
      add(LAYERS[0], {
        type: "circle", filter: ["==", ["get", "kind"], "closure"],
        paint: { "circle-radius": 14, "circle-color": "#d97706", "circle-opacity": 0.25, "circle-stroke-color": "#d97706", "circle-stroke-width": 2 },
      });
      add(LAYERS[1], {
        type: "line", filter: ["==", ["get", "kind"], "route"], layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#ffffff", "line-width": 10, "line-opacity": 0.9 },
      });
      add(LAYERS[2], {
        type: "line", filter: ["==", ["get", "kind"], "route"], layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": color, "line-width": 6 },
      });
      add(LAYERS[3], {
        type: "circle", filter: ["==", ["get", "kind"], "me"],
        paint: { "circle-radius": 16, "circle-color": "#007aff", "circle-opacity": 0.18 },
      });
      add(LAYERS[4], {
        type: "circle", filter: ["==", ["get", "kind"], "me"],
        paint: { "circle-radius": 7, "circle-color": "#007aff", "circle-stroke-color": "#ffffff", "circle-stroke-width": 3 },
      });
      if (position && follow.current) map.easeTo({ center: [position.lon, position.lat], zoom: Math.max(map.getZoom(), 15.5), duration: 600 });
    };
    const stop = whenStyleReady(map, apply);
    return stop;
  }, [map, route, position, closures, color]);

  useEffect(() => () => {
    if (map.getStyle()) removeMapSource(map, SOURCE, LAYERS);
  }, [map]);

  return null;
}
