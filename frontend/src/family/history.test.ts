import { describe, expect, it } from "vitest";
import { readHistory, type HistoryEntry, type HistoryStore } from "./history";

function memoryStore(entries: HistoryEntry[]): HistoryStore & { rows: HistoryEntry[] } {
  const s = {
    rows: entries.map((e, i) => ({ ...e, id: i + 1 })),
    all: async () => [...s.rows],
    add: async (e: HistoryEntry) => void s.rows.push({ ...e, id: s.rows.length + 1 }),
    remove: async (id: number) => void (s.rows = s.rows.filter((r) => r.id !== id)),
    clear: async () => void (s.rows = []),
  };
  return s;
}

describe("activity log", () => {
  it("returns newest first and deletes entries older than 30 days", async () => {
    const now = Date.UTC(2026, 10, 7);
    const day = 86_400_000;
    const store = memoryStore([
      { ts: now - 40 * day, kind: "walk", text: "old" },
      { ts: now - 2 * day, kind: "walk", text: "older" },
      { ts: now - day, kind: "followed", text: "newer" },
    ]);
    const rows = await readHistory(store, now);
    expect(rows.map((r) => r.text)).toEqual(["newer", "older"]);
    expect(store.rows.map((r) => r.text)).not.toContain("old");
  });

  it("clears everything", async () => {
    const store = memoryStore([{ ts: Date.now(), kind: "walk", text: "x" }]);
    await store.clear();
    expect(await readHistory(store)).toEqual([]);
  });
});
