// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { distanceM, SimGeo } from "./geo";
import type { GeoFix } from "./types";

const route: [number, number][] = [
  [53.52, -113.52],
  [53.52, -113.51],
  [53.521, -113.51],
];

function run(sim: SimGeo, ticks: number): GeoFix[] {
  const out: GeoFix[] = [];
  sim.start((p) => out.push(p));
  vi.advanceTimersByTime(ticks * 1000);
  sim.stop();
  return out;
}

describe("SimGeo", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-11-07T18:00:00Z"));
  });
  afterEach(() => vi.useRealTimers());

  it("emits every second and moves 80 m/min", () => {
    const sim = new SimGeo(route, { seed: 1 });
    const fixes = run(sim, 60);
    expect(fixes).toHaveLength(61);
    expect(sim.distanceAlong).toBeCloseTo(80, 6);
    expect(fixes.every((f) => f.accuracy_m === 5)).toBe(true);
    expect(fixes[1].ts - fixes[0].ts).toBe(1000);
  });

  it("jitters by at most 3 m per axis", () => {
    const sim = new SimGeo(route, { seed: 2 });
    const fixes = run(sim, 0);
    const d = distanceM([fixes[0].lat, fixes[0].lon], route[0]);
    expect(d).toBeLessThanOrEqual(Math.SQRT2 * 3 + 1e-9);
  });

  it("is deterministic for a seed", () => {
    const a = run(new SimGeo(route, { seed: 7, speedMultiplier: 5 }), 30);
    vi.setSystemTime(new Date("2026-11-07T18:00:00Z"));
    const b = run(new SimGeo(route, { seed: 7, speedMultiplier: 5 }), 30);
    expect(a).toEqual(b);
    const c = run(new SimGeo(route, { seed: 8, speedMultiplier: 5 }), 30);
    expect(c[3].lat).not.toBe(a[3].lat);
  });

  it("stops at the end of the route", () => {
    const sim = new SimGeo(route, { speedMultiplier: 100 });
    run(sim, 60);
    expect(sim.arrived).toBe(true);
    expect(sim.position).toEqual(route[2]);
    expect(sim.etaMin).toBe(0);
  });

  it("setRoute continues from the current position", () => {
    const sim = new SimGeo(route, { speedMultiplier: 10 });
    run(sim, 30); // 400 m east along the first leg
    const here = sim.position;
    const detour: [number, number][] = [
      [53.52005, -113.52],
      [53.52005, -113.5],
    ];
    sim.setRoute(detour);
    expect(distanceM(sim.position, here)).toBeLessThan(11);
    expect(sim.distanceAlong).toBeGreaterThan(300);
  });
});
