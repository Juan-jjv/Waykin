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

export function formatExposure(exposure: Interval, noun = "reported incidents"): string {
  return `≈ ${exposure.p50.toFixed(1)} ${noun} (${exposure.p10.toFixed(1)}–${exposure.p90.toFixed(1)})`;
}

export function formatDiff(diff: Interval | null): string | null {
  if (!diff) return null;
  if (diff.p50 >= 0) return "about the same or more";
  const p50 = Math.abs(diff.p50).toFixed(1);
  const p90 = Math.abs(diff.p90).toFixed(1);
  const p10 = Math.abs(diff.p10).toFixed(1);
  return `about ${p50} fewer (${p90} to ${p10} fewer)`;
}

/** One decimal place, the precision the panel shows report counts at. */
export function formatCount(value: number): string {
  return value.toFixed(1);
}

export function formatDistance(meters: number): string {
  return meters < 1000 ? `${Math.round(meters / 10) * 10} m` : `${(meters / 1000).toFixed(1)} km`;
}

export function formatMinutes(minutes: number): string {
  return `${Math.round(minutes)} min`;
}

export function formatExtra(minutes: number): string | null {
  const rounded = Math.round(minutes);
  if (rounded <= 0) return null;
  return `+${rounded} min`;
}
