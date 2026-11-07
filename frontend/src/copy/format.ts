import type { Interval } from "../api/types";

export function formatAsOf(iso: string): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

export function formatExposure(exposure: Interval): string {
  return `≈ ${exposure.p50.toFixed(1)} reported incidents (${exposure.p10.toFixed(1)}–${exposure.p90.toFixed(1)})`;
}

export function formatDiff(diff: Interval | null): string | null {
  if (!diff) return null;
  if (diff.p50 >= 0) return "about the same or more";
  const p50 = Math.abs(diff.p50).toFixed(1);
  const p90 = Math.abs(diff.p90).toFixed(1);
  const p10 = Math.abs(diff.p10).toFixed(1);
  return `about ${p50} fewer (${p90} to ${p10} fewer)`;
}

export function formatMinutes(minutes: number): string {
  return `${Math.round(minutes)} min`;
}

export function formatExtra(minutes: number): string | null {
  const rounded = Math.round(minutes);
  if (rounded <= 0) return null;
  return `+${rounded} min`;
}
