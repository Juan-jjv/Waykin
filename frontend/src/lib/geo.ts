// Position providers. RealGeo wraps the browser; SimGeo walks a route polyline with the same
// callback shape, so the walker screen has one code path for both.

import type { GeoFix, LatLonPair } from "./types";

export interface GeoProvider {
  start(cb: (p: { lat: number; lon: number; accuracy_m: number; ts: number }) => void): void;
  stop(): void;
}

export class RealGeo implements GeoProvider {
  private watchId: number | null = null;

  start(cb: (p: GeoFix) => void): void {
    this.stop();
    const geo = globalThis.navigator?.geolocation;
    if (!geo) throw new Error("Geolocation is unavailable (a secure context, https or localhost, is required)");
    this.watchId = geo.watchPosition(
      (pos) =>
        cb({
          lat: pos.coords.latitude,
          lon: pos.coords.longitude,
          accuracy_m: pos.coords.accuracy,
          ts: pos.timestamp || Date.now(),
        }),
      () => undefined, // errors surface as an absence of fixes; the UI shows "waiting for location"
      { enableHighAccuracy: true, maximumAge: 2000, timeout: 20000 },
    );
  }

  stop(): void {
    if (this.watchId !== null) globalThis.navigator?.geolocation?.clearWatch(this.watchId);
    this.watchId = null;
  }
}

// ---------------------------------------------------------------- geometry helpers
const M_PER_DEG_LAT = 111_320;
const SIM_SPEED_M_PER_MIN = 80; // WALK_SPEED_M_PER_MIN
const JITTER_M = 3;
const SIM_ACCURACY_M = 5;

function mPerDegLon(lat: number): number {
  return M_PER_DEG_LAT * Math.cos((lat * Math.PI) / 180);
}

/** Equirectangular distance in metres; fine at city scale. */
export function distanceM(a: LatLonPair, b: LatLonPair): number {
  const dy = (b[0] - a[0]) * M_PER_DEG_LAT;
  const dx = (b[1] - a[1]) * mPerDegLon((a[0] + b[0]) / 2);
  return Math.hypot(dx, dy);
}

/** Deterministic PRNG (mulberry32). */
export function mulberry32(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

class Polyline {
  readonly cum: number[];
  constructor(readonly pts: LatLonPair[]) {
    if (pts.length === 0) throw new Error("empty route geometry");
    this.cum = [0];
    for (let i = 1; i < pts.length; i++) this.cum.push(this.cum[i - 1] + distanceM(pts[i - 1], pts[i]));
  }
  get length(): number {
    return this.cum[this.cum.length - 1];
  }
  at(d: number): LatLonPair {
    const pts = this.pts;
    if (pts.length === 1 || d <= 0) return pts[0];
    if (d >= this.length) return pts[pts.length - 1];
    let i = 1;
    while (this.cum[i] < d) i++;
    const seg = this.cum[i] - this.cum[i - 1];
    const f = seg > 0 ? (d - this.cum[i - 1]) / seg : 0;
    const a = pts[i - 1];
    const b = pts[i];
    return [a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f];
  }
  /** Distance along the line of the point nearest to p. */
  project(p: LatLonPair): number {
    let best = 0;
    let bestD = Infinity;
    const kx = mPerDegLon(p[0]);
    for (let i = 1; i < this.pts.length; i++) {
      const a = this.pts[i - 1];
      const b = this.pts[i];
      const ax = (a[1] - p[1]) * kx, ay = (a[0] - p[0]) * M_PER_DEG_LAT;
      const bx = (b[1] - p[1]) * kx, by = (b[0] - p[0]) * M_PER_DEG_LAT;
      const vx = bx - ax, vy = by - ay;
      const len2 = vx * vx + vy * vy;
      const t = len2 > 0 ? Math.max(0, Math.min(1, -(ax * vx + ay * vy) / len2)) : 0;
      const d = Math.hypot(ax + vx * t, ay + vy * t);
      if (d < bestD) {
        bestD = d;
        best = this.cum[i - 1] + (this.cum[i] - this.cum[i - 1]) * t;
      }
    }
    return best;
  }
}

/**
 * Simulated walker: every `intervalMs` (default 1 s) it moves 80 m/min x speedMultiplier along the
 * polyline and emits a fix with seeded +-3 m jitter and accuracy_m = 5. Fully deterministic for a seed.
 * Stops advancing at the end of the route (keeps emitting the final point).
 */
export class SimGeo implements GeoProvider {
  private line: Polyline;
  private dist = 0;
  private tick = 0;
  private t0 = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private rand: () => number;
  private readonly speedMultiplier: number;
  private readonly intervalMs: number;
  private cb: ((p: GeoFix) => void) | null = null;

  constructor(geometry: [number, number][], o?: { speedMultiplier?: number; seed?: number; intervalMs?: number }) {
    this.line = new Polyline(geometry);
    this.speedMultiplier = o?.speedMultiplier ?? 1;
    this.intervalMs = o?.intervalMs ?? 1000;
    this.rand = mulberry32(o?.seed ?? 20261106);
  }

  /** Metres walked along the current route. */
  get distanceAlong(): number {
    return this.dist;
  }

  get arrived(): boolean {
    return this.dist >= this.line.length;
  }

  /** Remaining minutes at the simulated speed. */
  get etaMin(): number {
    return Math.max(0, this.line.length - this.dist) / (SIM_SPEED_M_PER_MIN * this.speedMultiplier);
  }

  /** Current (un-jittered) position on the route. */
  get position(): LatLonPair {
    return this.line.at(this.dist);
  }

  start(cb: (p: GeoFix) => void): void {
    this.stop();
    this.cb = cb;
    if (this.tick === 0) this.t0 = Date.now();
    this.emit();
    this.timer = setInterval(() => {
      this.dist = Math.min(this.line.length, this.dist + this.stepM());
      this.tick++;
      this.emit();
    }, this.intervalMs);
  }

  stop(): void {
    if (this.timer !== null) clearInterval(this.timer);
    this.timer = null;
  }

  /** Continue from the current position onto the new route. */
  setRoute(geometry: [number, number][]): void {
    const here = this.position;
    this.line = new Polyline(geometry);
    this.dist = this.line.project(here);
  }

  private stepM(): number {
    return ((SIM_SPEED_M_PER_MIN * this.speedMultiplier) / 60_000) * this.intervalMs;
  }

  private emit(): void {
    const [lat, lon] = this.position;
    const jn = (this.rand() * 2 - 1) * JITTER_M;
    const je = (this.rand() * 2 - 1) * JITTER_M;
    this.cb?.({
      lat: lat + jn / M_PER_DEG_LAT,
      lon: lon + je / mPerDegLon(lat),
      accuracy_m: SIM_ACCURACY_M,
      ts: this.t0 + this.tick * this.intervalMs,
    });
  }
}
