import type { ReactNode } from "react";
import { MapContainer, Rectangle, TileLayer } from "react-leaflet";
import type { LatLngBoundsExpression } from "leaflet";
import type { Provenance } from "../api/types";
import { ProvenanceBanner } from "./ProvenanceBanner";

// One constant for the tile URL; A4's CSP allows this host.
export const TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";
export const TILE_ATTRIBUTION = "&copy; OpenStreetMap contributors";

export function bboxBounds(bbox: number[]): LatLngBoundsExpression {
  const [w, s, e, n] = bbox;
  return [[s, w], [n, e]];
}

/** The map always renders the provenance banner: `provenance` is required, so it can't be left off. */
export function MapView({ provenance, bbox, showBbox = false, children }: {
  provenance: Provenance;
  bbox: number[];
  showBbox?: boolean;
  children?: ReactNode;
}) {
  return (
    <div className="map-wrap">
      <MapContainer bounds={bboxBounds(bbox)} className="map" zoomControl>
        <TileLayer url={TILE_URL} attribution={TILE_ATTRIBUTION} />
        {showBbox && <Rectangle bounds={bboxBounds(bbox)} pathOptions={{ color: "#64748b", weight: 1, fill: false, dashArray: "6 6" }} />}
        {children}
      </MapContainer>
      <ProvenanceBanner provenance={provenance} />
    </div>
  );
}
