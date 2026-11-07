// Activity log kept only on this device (IndexedDB). Never sent to the server. Entries older than 30 days are
// removed whenever the log is read.
import { HISTORY, idb } from "./idb";

export type HistoryKind = "walk" | "followed" | "family" | "alert";
export type HistoryEntry = { id?: number; ts: number; kind: HistoryKind; text: string };

export const HISTORY_DAYS = 30;

export interface HistoryStore {
  all(): Promise<HistoryEntry[]>;
  add(e: HistoryEntry): Promise<void>;
  remove(id: number): Promise<void>;
  clear(): Promise<void>;
}

export const deviceHistory: HistoryStore = {
  all: () => idb.all<HistoryEntry>(HISTORY),
  add: async (e) => void (await idb.put(HISTORY, e)),
  remove: async (id) => void (await idb.delete(HISTORY, id)),
  clear: async () => void (await idb.clear(HISTORY)),
};

/** Newest first, after removing entries older than HISTORY_DAYS. */
export async function readHistory(store: HistoryStore = deviceHistory, now = Date.now()): Promise<HistoryEntry[]> {
  const cutoff = now - HISTORY_DAYS * 86_400_000;
  const all = await store.all();
  for (const e of all) if (e.ts < cutoff && e.id !== undefined) await store.remove(e.id);
  return all.filter((e) => e.ts >= cutoff).sort((a, b) => b.ts - a.ts);
}

/** Best effort: a private window may block IndexedDB, and the walk must never fail because of the log. */
export function logActivity(kind: HistoryKind, text: string, store: HistoryStore = deviceHistory): void {
  store.add({ ts: Date.now(), kind, text }).catch(() => undefined);
}
