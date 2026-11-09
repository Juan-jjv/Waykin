import type { LatLon } from "../api/types";

export interface Station {
  id: string;
  name: string;
  agency: string;
  address: string;
  point: LatLon;
}

// City of Edmonton open data, "Police Stations" (data.edmonton.ca, dataset e7aq-scxv). The RCMP rows there repeat one
// headquarters under two neighbouring addresses, so it appears once here.
export const STATIONS: Station[] = [
  { id: "downtown", name: "Downtown Division", agency: "Edmonton Police Service", address: "9620 103A Ave NW", point: { lat: 53.547706, lon: -113.484817 } },
  { id: "northeast", name: "Northeast Division", agency: "Edmonton Police Service", address: "14203 50 St NW", point: { lat: 53.60504, lon: -113.417301 } },
  { id: "west", name: "West Division", agency: "Edmonton Police Service", address: "16505 100 Ave NW", point: { lat: 53.538808, lon: -113.606742 } },
  { id: "southeast", name: "Southeast Division", agency: "Edmonton Police Service", address: "104 Youville Dr E NW", point: { lat: 53.460001, lon: -113.426714 } },
  { id: "southwest", name: "Southwest Division", agency: "Edmonton Police Service", address: "1351 Windermere Way SW", point: { lat: 53.434012, lon: -113.616228 } },
  { id: "calder", name: "Calder Community Station", agency: "Edmonton Police Service", address: "12520 132 Ave NW", point: { lat: 53.593139, lon: -113.538658 } },
  { id: "rcmp-k", name: "RCMP K Division", agency: "Royal Canadian Mounted Police", address: "11140 109 St NW", point: { lat: 53.560798, lon: -113.510101 } },
];

/** Straight-line metres; plenty for ranking places across one city. */
export function distanceM(a: LatLon, b: LatLon): number {
  const rad = Math.PI / 180;
  const x = (b.lon - a.lon) * rad * Math.cos(((a.lat + b.lat) / 2) * rad);
  const y = (b.lat - a.lat) * rad;
  return Math.sqrt(x * x + y * y) * 6_371_000;
}

/** Stations nearest first when there's a reference point, otherwise in list order. */
export function rankStations(from: LatLon | null): { station: Station; meters: number | null }[] {
  const rows = STATIONS.map((station) => ({ station, meters: from ? distanceM(from, station.point) : null }));
  return from ? rows.sort((a, b) => (a.meters ?? 0) - (b.meters ?? 0)) : rows;
}
