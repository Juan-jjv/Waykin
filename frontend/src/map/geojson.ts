import type { FeatureCollection } from "geojson";
import type { GeoJSONSource, Map as MapLibreMap, StyleSpecification } from "maplibre-gl";

export function setGeoJson(map: MapLibreMap, id: string, data: FeatureCollection): void {
  const existing = map.getSource(id);
  if (existing?.type === "geojson") {
    (existing as GeoJSONSource).setData(data);
    return;
  }
  map.addSource(id, { type: "geojson", data });
}

export function removeMapSource(map: MapLibreMap, sourceId: string, layerIds: string[]): void {
  for (const layerId of layerIds) {
    if (map.getLayer(layerId)) map.removeLayer(layerId);
  }
  if (map.getSource(sourceId)) map.removeSource(sourceId);
}

export function toLngLatLine(geometry: number[][]): [number, number][] {
  return geometry.map(([lat, lon]) => [lon, lat]);
}

export function keepWaykinStyle(previous: StyleSpecification | undefined, next: StyleSpecification): StyleSpecification {
  if (!previous) return next;
  const sources = { ...next.sources };
  for (const [id, source] of Object.entries(previous.sources)) {
    if (id.startsWith("waykin-")) sources[id] = source;
  }
  const layers = [...next.layers, ...previous.layers.filter((layer) => layer.id.startsWith("waykin-"))];
  return { ...next, sources, layers };
}

export function whenStyleReady(map: MapLibreMap, apply: () => void): () => void {
  const run = () => {
    if (!map.getStyle()) return;
    apply();
  };
  map.on("style.load", run);
  if (map.isStyleLoaded()) run();
  return () => {
    map.off("style.load", run);
  };
}
