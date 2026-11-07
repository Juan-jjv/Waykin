import { createContext, useContext, type ReactNode } from "react";
import type { Map as MapLibreMap } from "maplibre-gl";

const MapContext = createContext<MapLibreMap | null>(null);

export function MapProvider({ map, children }: { map: MapLibreMap | null; children: ReactNode }) {
  return <MapContext.Provider value={map}>{children}</MapContext.Provider>;
}

export function useWaykinMap(): MapLibreMap {
  const map = useContext(MapContext);
  if (!map) throw new Error("Map is not ready");
  return map;
}
