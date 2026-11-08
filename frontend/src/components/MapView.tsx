import { useEffect, useRef, useState, type ReactNode } from "react";
import { Map as MapLibreMap, NavigationControl } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import { MapProvider } from "../map/context";
import { fitPadding } from "../map/fitPadding";
import { keepWaykinStyle, removeMapSource, setGeoJson, whenStyleReady } from "../map/geojson";
import { MAP_STYLES } from "../map/styles";
import { useAppearance } from "../theme/appearance";
import { AppearanceButton } from "./AppearanceButton";

interface MapViewProps {
  bbox: number[];
  showBBox: boolean;
  children?: ReactNode;
}

const BBOX_SOURCE = "waykin-bbox";
const BBOX_LAYERS = ["waykin-bbox-fill", "waykin-bbox-line"];

export function MapView({ bbox, showBBox, children }: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const { appearance } = useAppearance();
  const appearanceRef = useRef(appearance);
  appearanceRef.current = appearance;
  const appliedStyle = useRef(appearance);
  const [map, setMap] = useState<MapLibreMap | null>(null);
  const [west, south, east, north] = bbox;

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const style = appearanceRef.current;
    appliedStyle.current = style;
    const instance = new MapLibreMap({
      container,
      style: MAP_STYLES[style],
      center: [(west + east) / 2, (south + north) / 2],
      zoom: 13,
      minZoom: 9,
      maxZoom: 19,
      attributionControl: false,
    });
    instance.addControl(new NavigationControl({ showCompass: false, visualizePitch: false }), "top-left");
    instance.on("load", () => setMap(instance));
    const observer = new ResizeObserver(() => instance.resize());
    observer.observe(container);
    return () => {
      observer.disconnect();
      setMap(null);
      instance.remove();
    };
  }, [east, north, south, west]);

  useEffect(() => {
    if (!map) return;
    if (appliedStyle.current === appearance) return;
    appliedStyle.current = appearance;
    map.setStyle(MAP_STYLES[appearance], { diff: false, transformStyle: keepWaykinStyle });
  }, [appearance, map]);

  useEffect(() => {
    if (!map) return;
    const apply = () => {
      map.fitBounds(
        [
          [west, south],
          [east, north],
        ],
        { padding: fitPadding(), maxZoom: 16, duration: 0 },
      );
    };
    if (map.isStyleLoaded()) apply();
    else map.once("load", apply);
    const stop = () => map.off("load", apply);
    map.once("dragstart", stop);
    return () => {
      map.off("load", apply);
      map.off("dragstart", stop);
    };
  }, [map, west, south, east, north]);

  useEffect(() => {
    if (!map) return;
    const apply = () => {
      if (!showBBox) {
        removeMapSource(map, BBOX_SOURCE, BBOX_LAYERS);
        return;
      }
      const ring: [number, number][] = [
        [west, south],
        [east, south],
        [east, north],
        [west, north],
        [west, south],
      ];
      const data: FeatureCollection = {
        type: "FeatureCollection",
        features: [{ type: "Feature", properties: {}, geometry: { type: "Polygon", coordinates: [ring] } }],
      };
      setGeoJson(map, BBOX_SOURCE, data);
      if (!map.getLayer(BBOX_LAYERS[0])) {
        map.addLayer({
          id: BBOX_LAYERS[0],
          type: "fill",
          source: BBOX_SOURCE,
          paint: { "fill-color": "#64748b", "fill-opacity": 0.08 },
        });
      }
      if (!map.getLayer(BBOX_LAYERS[1])) {
        map.addLayer({
          id: BBOX_LAYERS[1],
          type: "line",
          source: BBOX_SOURCE,
          paint: { "line-color": "#64748b", "line-width": 2, "line-dasharray": [2, 1.4] },
        });
      }
      map.fitBounds(
        [
          [west, south],
          [east, north],
        ],
        { padding: fitPadding(), maxZoom: 16, duration: 500 },
      );
    };
    const stop = whenStyleReady(map, apply);
    return () => {
      stop();
      if (map.getStyle()) removeMapSource(map, BBOX_SOURCE, BBOX_LAYERS);
    };
  }, [map, showBBox, west, south, east, north]);

  return (
    <div className="map-frame">
      <div ref={containerRef} className="map-root" />
      <MapProvider map={map}>{map ? children : null}</MapProvider>
      <AppearanceButton />
    </div>
  );
}
