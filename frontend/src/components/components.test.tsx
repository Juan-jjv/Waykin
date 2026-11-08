import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Provenance, RoutesResponse } from "../api/types";
import { abstainCopy, strings } from "../copy/strings";
import { incidentRadius } from "./IncidentLayer";
import { ProvenanceBanner } from "./ProvenanceBanner";
import { RoutePanel } from "./RoutePanel";
import {
  SEVERITY_MAX, SEVERITY_MIN, SEVERITY_RAMP, severityColorExpression, severityOf, worstCategory,
} from "../map/colors";
import { abstainBody } from "../copy/strings";

const prov: Provenance = {
  source: "synthetic", source_label: "Synthetic data (demo)", as_of: "2026-10-31", window_days: 7, radius_m: 100,
  units: "reported incidents attributed to segments along this route, last 7 days", disclaimer: "Counts of reported incidents.",
};

function routes(status: "recommend" | "abstain", reason: RoutesResponse["decision"]["reason"] = null): RoutesResponse {
  const iv = { p10: 1, p50: 2, p90: 3, mean: 2 };
  const base = { geometry: [[53.5, -113.5], [53.51, -113.5]], edge_ids: [1], top_segments: [], explanation: "x",
    distance_m: 100, exposure: iv };
  return {
    mode: "walk",
    provenance: prov, origin_snapped: { lat: 53.5, lon: -113.5 }, destination_snapped: { lat: 53.51, lon: -113.5 },
    blocked_edge_count: 0,
    routes: [
      { ...base, route_id: "f", label: "fastest", minutes: 10, extra_minutes: 0, exposure_diff_vs_fastest: null, draws_better: null },
      { ...base, route_id: "b", label: "lower_exposure", minutes: 11, extra_minutes: 1, exposure_diff_vs_fastest: { ...iv, p50: -1 }, draws_better: 471 },
    ],
    decision: { status, recommended_route_id: status === "recommend" ? "b" : null, reason, message: "msg",
      radius_sensitive: null, radius_decisions: null, n_draws: 500,
      thresholds: { min_reduction: 0.15, min_draw_share: 0.9, max_extra_time: 0.25 } },
  };
}

const noop = () => undefined;
const panel = (data: RoutesResponse, selectedId: string) => (
  <RoutePanel response={data} selectedId={selectedId} segmentRouteId={null} onSelect={noop}
    onShowSegments={noop} onStartWalk={noop} walkNote={null} />
);

describe("incident severity shades", () => {
  const sev = { homicide: 5, assault: 3, indecent_act: 1.5, theft: 1 };
  it("a dot takes the shade of its most serious report", () => {
    expect(severityOf({ theft: 9, homicide: 1 }, sev)).toBe(5);
    expect(severityOf({ indecent_act: 2 }, sev)).toBe(1.5);
    expect(severityOf({ theft: 0, assault: 0 }, sev)).toBe(1);
    expect(severityOf({ unknown: 3 }, {})).toBe(1);
    expect(worstCategory({ theft: 4, assault: 1 }, sev)).toBe("assault");
  });
  it("the ramp runs light to dark with one stop per level", () => {
    expect(SEVERITY_RAMP.light).toHaveLength(SEVERITY_MAX - SEVERITY_MIN + 1);
    expect(severityColorExpression("light").slice(0, 5)).toEqual(["interpolate", ["linear"], ["get", "sev"], 1, "#fca5a5"]);
  });
});

describe("route copy", () => {
  it("abstain copy uses the server's time cap", () => {
    expect(abstainBody("too_costly", 0.4)).toContain("more than 40% to your travel time");
  });
});

describe("components", () => {
  it("incident dots grow with the count, up to a cap, and the text states counts", () => {
    expect(incidentRadius(9)).toBeGreaterThan(incidentRadius(1));
    expect(incidentRadius(100000)).toBe(16);
    expect(strings.incidentCount(1)).toBe("1 reported incident, last 30 days");
    expect(strings.incidentCount(3)).toBe("3 reported incidents, last 30 days");
    expect(strings.incidentCategory("break_and_enter", 2)).toBe("break and enter: 2");
  });

  it("ProvenanceBanner shows the source, date and units", () => {
    render(<ProvenanceBanner provenance={prov} />);
    expect(screen.getByText(/Synthetic data \(demo\) · as of Oct 31, 2026/)).toBeTruthy();
    expect(screen.getByText(prov.units)).toBeTruthy();
  });

  it("RoutePanel marks the recommendation and shows stability as a count", () => {
    render(panel(routes("recommend"), "b"));
    expect(screen.getByText("Recommended: Lower-exposure")).toBeTruthy();
    expect(screen.getByText("Holds in 471 of 500 simulations")).toBeTruthy();
  });

  it.each(["thin_data", "indistinguishable", "too_costly", "no_alternative"] as const)("abstain card for %s", (reason) => {
    render(panel(routes("abstain", reason), "f"));
    expect(screen.getByText(abstainCopy[reason].headline)).toBeTruthy();
  });

  it("lint:words fails on a banned word", () => {
    const dir = mkdtempSync(join(tmpdir(), "lw-"));
    writeFileSync(join(dir, "bad.ts"), "const s = 'a dangerous street';\n"); // lint-words: ignore
    expect(() => execFileSync("node", ["tools/lint-words.mjs", dir], { stdio: "pipe" })).toThrow();
  });
});
