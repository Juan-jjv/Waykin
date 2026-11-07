import { expect, it } from "vitest";
import { SimGeo } from "./geo";

const route: [number, number][] = [[53.515, -113.525], [53.515, -113.52], [53.52, -113.52]];

it("is deterministic for a seed", () => {
  const a = new SimGeo(route, { seed: 1 });
  const b = new SimGeo(route, { seed: 1 });
  for (let i = 0; i < 5; i++) {
    const [p, q] = [a.tick(), b.tick()];
    expect([p.lat, p.lon]).toEqual([q.lat, q.lon]);
  }
});

it("stops at the end of the route", () => {
  const g = new SimGeo(route, { speedMultiplier: 1000 });
  for (let i = 0; i < 20; i++) g.tick();
  const p = g.tick();
  expect(p.lat).toBeCloseTo(53.52, 3);
  expect(p.lon).toBeCloseTo(-113.52, 3);
});

it("continues from the current point after setRoute", () => {
  const g = new SimGeo(route, { speedMultiplier: 5, intervalMs: 1000 });
  g.tick();                                      // one tick = 80/60 × 5 × 1 s ≈ 6.67 m
  const here = g.positionAt((80 / 60) * 5);
  g.setRoute([[53.516, -113.524]]);
  expect(g.positionAt(0)).toEqual(here);
  expect(g.positionAt(1e9)).toEqual([53.516, -113.524]);
});
