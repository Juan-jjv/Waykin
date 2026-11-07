// Owner: A1 (moved from A4 in spec v2). One callback shape for a real phone and the simulated walker.
export type GeoPoint = { lat: number; lon: number; accuracy_m: number; ts: number };

export interface GeoProvider {
  start(cb: (p: GeoPoint) => void): void;
  stop(): void;
}

export class RealGeo implements GeoProvider {
  private id: number | null = null;
  start(cb: (p: GeoPoint) => void): void {
    this.id = navigator.geolocation.watchPosition(
      (p) => cb({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy_m: p.coords.accuracy, ts: p.timestamp }),
      () => undefined,
      { enableHighAccuracy: true, maximumAge: 2000 },
    );
  }
  stop(): void {
    if (this.id !== null) navigator.geolocation.clearWatch(this.id);
    this.id = null;
  }
}

const WALK_M_PER_MIN = 80;
const R = 6371000;

function dist(a: [number, number], b: [number, number]): number {
  const dLat = ((b[0] - a[0]) * Math.PI) / 180;
  const dLon = ((b[1] - a[1]) * Math.PI) / 180;
  const x = dLon * Math.cos((((a[0] + b[0]) / 2) * Math.PI) / 180);
  return Math.sqrt(x * x + dLat * dLat) * R;
}

/** Deterministic pseudo-random numbers (mulberry32). */
function rng(seed: number) {
  let s = seed >>> 0;
  return () => {
    s = (s + 0x6d2b79f5) >>> 0;
    let t = s;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Walks the polyline at 80 m/min × speedMultiplier, emitting every intervalMs with seeded ±3 m jitter. */
export class SimGeo implements GeoProvider {
  private route: [number, number][];
  private travelled = 0;
  private timer: ReturnType<typeof setInterval> | null = null;
  private rand: () => number;
  private speed: number;
  private intervalMs: number;
  private last: [number, number];

  constructor(geometry: [number, number][], o: { speedMultiplier?: number; seed?: number; intervalMs?: number } = {}) {
    this.route = geometry;
    this.speed = o.speedMultiplier ?? 1;
    this.intervalMs = o.intervalMs ?? 1000;
    this.rand = rng(o.seed ?? 20261106);
    this.last = geometry[0];
  }

  /** Continue from the current position onto a new route. */
  setRoute(geometry: [number, number][]): void {
    this.route = [this.last, ...geometry];
    this.travelled = 0;
  }

  /** Position after `metres` along the route (clamped to the end). */
  positionAt(metres: number): [number, number] {
    let left = metres;
    for (let i = 0; i + 1 < this.route.length; i++) {
      const d = dist(this.route[i], this.route[i + 1]);
      if (left <= d && d > 0) {
        const f = left / d;
        return [this.route[i][0] + f * (this.route[i + 1][0] - this.route[i][0]),
          this.route[i][1] + f * (this.route[i + 1][1] - this.route[i][1])];
      }
      left -= d;
    }
    return this.route[this.route.length - 1];
  }

  tick(): GeoPoint {
    this.travelled += (WALK_M_PER_MIN / 60) * this.speed * (this.intervalMs / 1000);
    const [lat, lon] = this.positionAt(this.travelled);
    this.last = [lat, lon];
    const j = () => (this.rand() * 2 - 1) * 3; // ±3 m
    return { lat: lat + j() / 111320, lon: lon + j() / (111320 * Math.cos((lat * Math.PI) / 180)), accuracy_m: 5, ts: Date.now() };
  }

  start(cb: (p: GeoPoint) => void): void {
    this.stop();
    cb(this.tick());
    this.timer = setInterval(() => cb(this.tick()), this.intervalMs);
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer);
    this.timer = null;
  }
}
