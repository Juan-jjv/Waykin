// Walk alerts, decided on the walker's own device. The server never sees why an alert fired: alerts travel inside
// the encrypted update. Pure functions and one small class, so every rule is unit-tested with simulated traces.

export type AlertKind = "arrived" | "stopped" | "off_route" | "overdue" | "rerouted" | "duress";
export type Fix = { lat: number; lon: number; ts: number };
type LatLonPair = [number, number];

export const ALERT_RULES = {
  arrivedM: 40,                 // within this of the destination
  stoppedM: 25,                 // moved less than this ...
  stoppedMs: 5 * 60_000,        // ... in this long
  nearEndsM: 60,                // and not this close to the start or the destination
  offRouteM: 75,                // farther than this from the route ...
  offRouteMs: 60_000,           // ... for this long
  overdueFactor: 1.5,           // later than start + ETA × this ...
  overdueGraceMs: 5 * 60_000,   // ... plus this
};

const R = 6371000;

export function metres(a: LatLonPair, b: LatLonPair): number {
  const dLat = ((b[0] - a[0]) * Math.PI) / 180;
  const dLon = ((b[1] - a[1]) * Math.PI) / 180;
  const x = dLon * Math.cos((((a[0] + b[0]) / 2) * Math.PI) / 180);
  return Math.sqrt(x * x + dLat * dLat) * R;
}

/** Shortest distance in metres from a point to a polyline of [lat, lon] pairs (local flat projection). */
export function distanceToRoute(p: LatLonPair, line: number[][]): number {
  if (line.length === 0) return Infinity;
  if (line.length === 1) return metres(p, line[0] as LatLonPair);
  const kx = Math.cos((p[0] * Math.PI) / 180) * (Math.PI / 180) * R;
  const ky = (Math.PI / 180) * R;
  const px = p[1] * kx;
  const py = p[0] * ky;
  let best = Infinity;
  for (let i = 0; i + 1 < line.length; i++) {
    const ax = line[i][1] * kx, ay = line[i][0] * ky, bx = line[i + 1][1] * kx, by = line[i + 1][0] * ky;
    const dx = bx - ax, dy = by - ay;
    const len2 = dx * dx + dy * dy;
    const t = len2 > 0 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) : 0;
    best = Math.min(best, Math.hypot(px - (ax + t * dx), py - (ay + t * dy)));
  }
  return best;
}

/** Metres left to walk: distance to the route, then along it from the closest point to its end. */
export function remainingMetres(p: LatLonPair, line: number[][]): number {
  if (line.length < 2) return line.length ? metres(p, line[0] as LatLonPair) : 0;
  let bestI = 0;
  let bestD = Infinity;
  for (let i = 0; i < line.length; i++) {
    const d = metres(p, line[i] as LatLonPair);
    if (d < bestD) {
      bestD = d;
      bestI = i;
    }
  }
  let rest = 0;
  for (let i = bestI; i + 1 < line.length; i++) rest += metres(line[i] as LatLonPair, line[i + 1] as LatLonPair);
  return bestD + rest;
}

export class AlertMonitor {
  private trail: Fix[] = [];
  private fired = new Set<AlertKind>();
  private offSince: number | null = null;
  private stoppedAt: LatLonPair | null = null;
  private route: number[][];
  private deadline: number;

  constructor(private o: { route: number[][]; start: LatLonPair; destination: LatLonPair; startTs: number; etaMin: number },
              private rules = ALERT_RULES) {
    this.route = o.route;
    this.deadline = o.startTs + o.etaMin * 60_000 * rules.overdueFactor + rules.overdueGraceMs;
  }

  /** After a reroute: follow the new line, and allow the off-route alert to fire again later. */
  setRoute(route: number[][], etaMin: number, nowTs: number): void {
    this.route = route;
    this.offSince = null;
    this.fired.delete("off_route");
    this.deadline = Math.max(this.deadline, nowTs + etaMin * 60_000 * this.rules.overdueFactor + this.rules.overdueGraceMs);
  }

  /** Feed one position; returns the alerts that start now (each fires once until its condition clears). */
  update(f: Fix): AlertKind[] {
    const r = this.rules;
    const here: LatLonPair = [f.lat, f.lon];
    const out: AlertKind[] = [];
    this.trail.push(f);
    while (this.trail.length > 2 && this.trail[1].ts <= f.ts - r.stoppedMs) this.trail.shift();

    if (!this.fired.has("arrived") && metres(here, this.o.destination) <= r.arrivedM) {
      this.fired.add("arrived");
      return ["arrived"];
    }

    const old = this.trail[0];
    const nearEnds = metres(here, this.o.start) < r.nearEndsM || metres(here, this.o.destination) < r.nearEndsM;
    if (old && f.ts - old.ts >= r.stoppedMs && metres(here, [old.lat, old.lon]) < r.stoppedM && !nearEnds) {
      if (!this.fired.has("stopped")) {
        this.fired.add("stopped");
        this.stoppedAt = here;
        out.push("stopped");
      }
    } else if (this.stoppedAt && metres(here, this.stoppedAt) > 2 * r.stoppedM) {
      this.fired.delete("stopped");
      this.stoppedAt = null;
    }

    if (distanceToRoute(here, this.route) > r.offRouteM) {
      this.offSince ??= f.ts;
      if (f.ts - this.offSince >= r.offRouteMs && !this.fired.has("off_route")) {
        this.fired.add("off_route");
        out.push("off_route");
      }
    } else {
      this.offSince = null;
      this.fired.delete("off_route");
    }

    if (!this.fired.has("overdue") && f.ts > this.deadline) {
      this.fired.add("overdue");
      out.push("overdue");
    }
    return out;
  }
}
