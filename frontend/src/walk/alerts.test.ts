import { describe, expect, it } from "vitest";
import { AlertMonitor, distanceToRoute, metres, remainingMetres } from "./alerts";

// A straight 1 km walk north. 0.001° of latitude ≈ 111 m.
const START: [number, number] = [53.51, -113.52];
const END: [number, number] = [53.519, -113.52];
const ROUTE = [START, [53.5145, -113.52], END];
const MIN = 60_000;

function monitor(etaMin = 13) {
  return new AlertMonitor({ route: ROUTE, start: START, destination: END, startTs: 0, etaMin });
}

describe("geometry", () => {
  it("measures distances to a route and what is left to walk", () => {
    expect(metres(START, END)).toBeGreaterThan(990);
    expect(metres(START, END)).toBeLessThan(1010);
    expect(distanceToRoute([53.5145, -113.519], ROUTE)).toBeGreaterThan(60);
    expect(distanceToRoute([53.5145, -113.52], ROUTE)).toBeLessThan(1);
    expect(remainingMetres(START, ROUTE)).toBeCloseTo(metres(START, END), -1);
  });
});

describe("AlertMonitor", () => {
  it("fires arrived once near the destination", () => {
    const m = monitor();
    expect(m.update({ lat: 53.5145, lon: -113.52, ts: 5 * MIN })).toEqual([]);
    expect(m.update({ lat: 53.5188, lon: -113.52, ts: 10 * MIN })).toEqual(["arrived"]);
    expect(m.update({ lat: 53.519, lon: -113.52, ts: 11 * MIN })).toEqual([]);
  });

  it("fires stopped after five minutes in one place mid-route, and again only after moving on", () => {
    const m = monitor(60);
    const mid = { lat: 53.5145, lon: -113.52 };
    expect(m.update({ ...mid, ts: 0 })).toEqual([]);
    expect(m.update({ ...mid, ts: 4 * MIN })).toEqual([]);
    expect(m.update({ ...mid, ts: 5 * MIN })).toEqual(["stopped"]);
    expect(m.update({ ...mid, ts: 6 * MIN })).toEqual([]);
    expect(m.update({ lat: 53.516, lon: -113.52, ts: 7 * MIN })).toEqual([]);     // walked on: reset
    expect(m.update({ lat: 53.516, lon: -113.52, ts: 12 * MIN })).toEqual(["stopped"]);
  });

  it("does not call a pause at the start a stop", () => {
    const m = monitor(60);
    m.update({ lat: START[0], lon: START[1], ts: 0 });
    expect(m.update({ lat: START[0], lon: START[1], ts: 6 * MIN })).toEqual([]);
  });

  it("fires off_route only after a minute away from the route", () => {
    const m = monitor(60);
    const off = { lat: 53.5145, lon: -113.5185 };   // about 100 m east
    expect(m.update({ ...off, ts: 0 })).toEqual([]);
    expect(m.update({ ...off, ts: 30_000 })).toEqual([]);
    expect(m.update({ lat: off.lat + 0.0003, lon: off.lon, ts: 61_000 })).toEqual(["off_route"]);
    expect(m.update({ lat: 53.5152, lon: -113.52, ts: 90_000 })).toEqual([]);     // back on route: clears
  });

  it("fires overdue after start + ETA × 1.5 + 5 minutes", () => {
    const m = monitor(10);   // deadline at 20 minutes
    expect(m.update({ lat: 53.511, lon: -113.52, ts: 19 * MIN })).toEqual([]);
    expect(m.update({ lat: 53.512, lon: -113.52, ts: 21 * MIN })).toEqual(["overdue"]);
  });

  it("a reroute extends the deadline and re-arms off_route", () => {
    const m = monitor(10);
    m.setRoute([[53.512, -113.52], END], 30, 15 * MIN);
    expect(m.update({ lat: 53.512, lon: -113.52, ts: 21 * MIN })).toEqual([]);
  });
});
