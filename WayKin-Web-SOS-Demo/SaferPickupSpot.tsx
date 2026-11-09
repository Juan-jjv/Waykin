import { useMemo, useState } from "react";
import "./safer-pickup.css";

type Spot = { id: string; name: string; kind: string; address: string; lat: number; lon: number; open: string; staffed: boolean };
type Position = { lat: number; lon: number };

// Sample places for a self-contained demo. Replace with a verified places API before real use.
const SAMPLE_SPOTS: Spot[] = [
  { id: "campus-help", name: "Campus Safety Desk", kind: "Campus support", address: "University Centre, Main Entrance", lat: 49.8079, lon: -97.1340, open: "Open 24 hours", staffed: true },
  { id: "market", name: "Convenience Market", kind: "Open business", address: "Pembina Highway near University Crescent", lat: 49.8061, lon: -97.1377, open: "Open until 11:00 PM", staffed: true },
  { id: "library", name: "Public Library", kind: "Public building", address: "Dafoe Road, University of Manitoba", lat: 49.8090, lon: -97.1323, open: "Open until 8:00 PM", staffed: true },
];

/** Demo feature: suggests nearby predefined staffed places and opens walking directions. */
export function SaferPickupSpot() {
  const [position, setPosition] = useState<Position | null>(null);
  const [status, setStatus] = useState("Use your location to find nearby sample pickup spots.");
  const [loading, setLoading] = useState(false);

  const spots = useMemo(() => [...SAMPLE_SPOTS].sort((a, b) =>
    position ? distanceKm(position, a) - distanceKm(position, b) : 0), [position]);

  function locate() {
    if (!navigator.geolocation) { setStatus("Location is unavailable in this browser."); return; }
    setLoading(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { setPosition({ lat: p.coords.latitude, lon: p.coords.longitude }); setStatus("Sorted by distance from your current location."); setLoading(false); },
      () => { setStatus("Could not access location. Allow location in your browser settings and try again."); setLoading(false); },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 60000 },
    );
  }

  function directions(spot: Spot) {
    const dest = `${spot.lat},${spot.lon}`;
    const origin = position ? `${position.lat},${position.lon}` : "";
    window.open(`https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(origin)}&destination=${encodeURIComponent(dest)}&travelmode=walking`, "_blank", "noopener,noreferrer");
  }

  return <section className="pickup-demo">
    <header className="pickup-head"><span className="pickup-icon">⌖</span><div><p className="pickup-eyebrow">WAYKIN SUPPORT</p><h1>Find a safer place nearby</h1></div></header>
    <p className="pickup-lede">Get directions to a sample staffed or public location if you want to move somewhere with people around.</p>
    <button className="pickup-locate" onClick={locate} disabled={loading}>{loading ? "Finding your location…" : "Use my current location"}</button>
    <p className="pickup-status" aria-live="polite">{status}</p>
    <div className="pickup-list">{spots.map((spot) => <article className="pickup-card" key={spot.id}>
      <span className="pickup-place-icon">{spot.kind === "Campus support" ? "＋" : "⌂"}</span>
      <div className="pickup-info"><span className="pickup-kind">{spot.kind}</span><h2>{spot.name}</h2><p>{spot.address}</p>
        <div className="pickup-meta"><span className="open-dot" />{spot.open}{position && <span> · {distanceKm(position, spot).toFixed(1)} km away</span>}</div>
        <button className="pickup-directions" onClick={() => directions(spot)}>Walking directions ↗</button>
      </div>
    </article>)}</div>
    <p className="pickup-disclaimer">Demo locations only. Hours, staffing, accessibility, and safety have not been verified. For immediate danger, contact local emergency services.</p>
  </section>;
}

function distanceKm(a: Position, b: Position) {
  const rad = (d: number) => d * Math.PI / 180;
  const dLat = rad(b.lat - a.lat), dLon = rad(b.lon - a.lon);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(rad(a.lat)) * Math.cos(rad(b.lat)) * Math.sin(dLon / 2) ** 2;
  return 6371 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h));
}
