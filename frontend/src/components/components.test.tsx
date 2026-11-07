import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type { Provenance, RoutesResponse } from "../api/types";
import { ABSTAIN } from "../copy/strings";
import { ProvenanceBanner } from "./ProvenanceBanner";
import { RoutePanel } from "./RoutePanel";

const prov: Provenance = {
  source: "synthetic", source_label: "Synthetic data (demo)", as_of: "2026-10-31", window_days: 90, radius_m: 100,
  units: "reported incidents attributed to segments along this route, last 90 days", disclaimer: "Counts of reported incidents.",
};

function routes(status: "recommend" | "abstain", reason: RoutesResponse["decision"]["reason"] = null): RoutesResponse {
  const iv = { p10: 1, p50: 2, p90: 3, mean: 2 };
  const base = { geometry: [[53.5, -113.5], [53.51, -113.5]], edge_ids: [1], top_segments: [], explanation: "x",
    distance_m: 100, exposure: iv };
  return {
    provenance: prov, origin_snapped: { lat: 53.5, lon: -113.5 }, destination_snapped: { lat: 53.51, lon: -113.5 },
    blocked_edge_count: 0,
    routes: [
      { ...base, route_id: "f", label: "fastest", minutes: 10, extra_minutes: 0, exposure_diff_vs_fastest: null, draws_better: null },
      { ...base, route_id: "b", label: "balanced", minutes: 11, extra_minutes: 1, exposure_diff_vs_fastest: { ...iv, p50: -1 }, draws_better: 471 },
    ],
    decision: { status, recommended_route_id: status === "recommend" ? "b" : null, reason, message: "msg",
      radius_sensitive: null, radius_decisions: null, n_draws: 500,
      thresholds: { min_reduction: 0.15, min_draw_share: 0.9, max_extra_time: 0.25 } },
  };
}

describe("components", () => {
  it("ProvenanceBanner shows the source and the synthetic badge", () => {
    render(<ProvenanceBanner provenance={prov} />);
    expect(screen.getByText("Synthetic data (demo)")).toBeTruthy();
    expect(screen.getByText("SYNTHETIC DATA")).toBeTruthy();
  });

  it("RoutePanel marks the recommendation and shows stability as a count", () => {
    render(<RoutePanel data={routes("recommend")} selectedId="b" onSelect={() => undefined} />);
    expect(screen.getByText("Recommended: Balanced")).toBeTruthy();
    expect(screen.getByText("Holds in 471 of 500 simulations")).toBeTruthy();
  });

  it.each(["thin_data", "indistinguishable", "too_costly", "no_alternative"] as const)("abstain card for %s", (reason) => {
    render(<RoutePanel data={routes("abstain", reason)} selectedId="f" onSelect={() => undefined} />);
    expect(screen.getByText(ABSTAIN[reason].headline)).toBeTruthy();
  });

  it("lint:words fails on a banned word", () => {
    const dir = mkdtempSync(join(tmpdir(), "lw-"));
    writeFileSync(join(dir, "bad.ts"), "const s = 'a dangerous street';\n"); // lint-words: ignore
    expect(() => execFileSync("node", ["tools/lint-words.mjs", dir], { stdio: "pipe" })).toThrow();
  });
});
