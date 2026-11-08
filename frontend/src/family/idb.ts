// Tiny IndexedDB wrapper for things that must stay on this device: the device's private key and the activity log.
// Nothing stored here is ever sent to the server.

const DB_NAME = "waykin";
const DB_VERSION = 1;
export const KEYS = "keys";
export const HISTORY = "history";

let opening: Promise<IDBDatabase> | null = null;

function open(): Promise<IDBDatabase> {
  if (!opening) {
    opening = new Promise((resolve, reject) => {
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const db = req.result;
        if (!db.objectStoreNames.contains(KEYS)) db.createObjectStore(KEYS);
        if (!db.objectStoreNames.contains(HISTORY)) db.createObjectStore(HISTORY, { keyPath: "id", autoIncrement: true });
      };
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => {
        opening = null;
        reject(req.error);
      };
    });
  }
  return opening;
}

async function run<T>(store: string, mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(store, mode).objectStore(store));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export const idb = {
  get: <T>(store: string, key: IDBValidKey) => run<T | undefined>(store, "readonly", (s) => s.get(key)),
  put: (store: string, value: unknown, key?: IDBValidKey) => run(store, "readwrite", (s) => s.put(value, key)),
  delete: (store: string, key: IDBValidKey) => run(store, "readwrite", (s) => s.delete(key)),
  all: <T>(store: string) => run<T[]>(store, "readonly", (s) => s.getAll()),
  clear: (store: string) => run(store, "readwrite", (s) => s.clear()),
};
