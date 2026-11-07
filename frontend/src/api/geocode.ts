import type { LatLon } from "./types";

// Public OpenStreetMap geocoder. A4's CSP (backend/waykin/main.py) must allow this host.
const PHOTON = "https://photon.komoot.io/api/";

export interface Place {
  label: string;
  point: LatLon;
}

interface PhotonFeature {
  geometry: { coordinates: [number, number] };
  properties: {
    name?: string;
    housenumber?: string;
    street?: string;
    district?: string;
    locality?: string;
    city?: string;
  };
}

export async function searchPlaces(query: string, bbox: number[], signal?: AbortSignal): Promise<Place[]> {
  const [west, south, east, north] = bbox;
  const params = new URLSearchParams({
    q: query,
    limit: "6",
    lang: "en",
    bbox: `${west},${south},${east},${north}`,
    lat: String((south + north) / 2),
    lon: String((west + east) / 2),
  });
  const response = await fetch(`${PHOTON}?${params}`, { signal });
  if (!response.ok) throw new Error("search");
  const body = (await response.json()) as { features?: PhotonFeature[] };
  const seen = new Set<string>();
  const places: Place[] = [];
  for (const feature of body.features ?? []) {
    const [lon, lat] = feature.geometry.coordinates;
    const label = placeLabel(feature.properties);
    if (!label || seen.has(label)) continue;
    seen.add(label);
    places.push({ label, point: { lat, lon } });
  }
  return places;
}

export function insideBBox(point: LatLon, bbox: number[]): boolean {
  const [west, south, east, north] = bbox;
  return point.lon >= west && point.lon <= east && point.lat >= south && point.lat <= north;
}

function placeLabel(p: PhotonFeature["properties"]): string {
  const street = [p.housenumber, p.street].filter(Boolean).join(" ");
  const parts = [p.name, street, p.district ?? p.locality ?? p.city].filter(Boolean);
  return [...new Set(parts)].join(", ");
}
