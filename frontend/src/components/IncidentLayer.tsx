import { useEffect } from "react";
import { Popup, type MapLayerMouseEvent } from "maplibre-gl";
import type { FeatureCollection } from "geojson";
import type { IncidentPoint } from "../api/types";
import { strings } from "../copy/strings";
import { INCIDENT_COLORS } from "../map/colors";
import { useWaykinMap } from "../map/context";
import { removeMapSource, setGeoJson, whenStyleReady } from "../map/geojson";
import { useAppearance } from "../theme/appearance";

const SOURCE = "waykin-incidents";
const LAYER = "waykin-incidents";

/** Grows with the count but stays capped, so a busy intersection doesn't cover its neighbours. */
export function incidentRadius(count: number): number {
  return Math.min(4 + Math.sqrt(count) * 1.5, 16);
}

export function IncidentLayer({ points, windowLabel }: { points: IncidentPoint[]; windowLabel: string }) {
  const map = useWaykinMap();
  const { appearance } = useAppearance();

  useEffect(() => {
    const popup = new Popup({ closeButton: false, closeOnClick: true, className: "wk-popup", offset: 14 });
    const show = (event: MapLayerMouseEvent) => {
      const feature = event.features?.[0];
      const count = Number(feature?.properties?.count ?? 0);
      const detail = String(feature?.properties?.detail ?? "");
      const node = document.createElement("div");
      const text = strings.incidentCount(count, windowLabel);
      node.textContent = detail ? `${text} (${detail})` : text;
      popup.setLngLat(event.lngLat).setDOMContent(node).addTo(map);
    };
    const onEnter = () => {
      map.getCanvas().style.cursor = "pointer";
    };
    const onLeave = () => {
      map.getCanvas().style.cursor = "";
      popup.remove();
    };
    const apply = () => {
      const data: FeatureCollection = {
        type: "FeatureCollection",
        features: points.map((point) => ({
          type: "Feature",
          properties: {
            count: point.count,
            radius: incidentRadius(point.count),
            detail: Object.entries(point.by_category)
              .filter(([, count]) => count > 0)
              .map(([name, count]) => strings.incidentCategory(name, count))
              .join(", "),
          },
          geometry: { type: "Point", coordinates: [point.lon, point.lat] },
        })),
      };
      setGeoJson(map, SOURCE, data);
      if (!map.getLayer(LAYER)) {
        map.addLayer({
          id: LAYER,
          type: "circle",
          source: SOURCE,
          paint: {
            "circle-radius": ["interpolate", ["linear"], ["zoom"], 10, ["*", ["get", "radius"], 0.3], 15, ["get", "radius"]],
            "circle-color": INCIDENT_COLORS[appearance].fill,
            "circle-opacity": 0.85,
            "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 10, 0.25, 14, 1],
            "circle-stroke-color": INCIDENT_COLORS[appearance].stroke,
          },
        });
      }
      map.off("click", LAYER, show);
      map.off("mouseenter", LAYER, onEnter);
      map.off("mousemove", LAYER, show);
      map.off("mouseleave", LAYER, onLeave);
      map.on("click", LAYER, show);
      map.on("mouseenter", LAYER, onEnter);
      map.on("mousemove", LAYER, show);
      map.on("mouseleave", LAYER, onLeave);
    };
    const stop = whenStyleReady(map, apply);
    return () => {
      stop();
      map.off("click", LAYER, show);
      map.off("mouseenter", LAYER, onEnter);
      map.off("mousemove", LAYER, show);
      map.off("mouseleave", LAYER, onLeave);
      popup.remove();
      if (map.getStyle()) removeMapSource(map, SOURCE, [LAYER]);
    };
  }, [map, points, appearance, windowLabel]);

  return null;
}

export function IncidentToggle({ on, onChange }: { on: boolean; onChange: (next: boolean) => void }) {
  return (
    <div className="row-between">
      <span>{strings.incidents}</span>
      <button
        type="button"
        role="switch"
        className={on ? "switch on" : "switch"}
        aria-checked={on}
        aria-label={strings.incidentsOn}
        onClick={() => onChange(!on)}
      >
        <span className="switch-knob" />
      </button>
    </div>
  );
}
