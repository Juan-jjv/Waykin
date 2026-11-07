import { beforeEach, describe, expect, it, vi } from "vitest";

const store = new Map<string, unknown>();
const uploads: string[] = [];

vi.mock("./idb", () => ({
  KEYS: "keys",
  idb: {
    get: async (_s: string, k: string) => store.get(k),
    put: async (_s: string, v: unknown, k: string) => void store.set(k, v),
  },
}));
vi.mock("./api", () => ({ accountApi: { setPublicKey: async (k: string) => void uploads.push(k) } }));

const { ensureDeviceKey, familySecret } = await import("./session");
const { newSecret, wrapForMember } = await import("./keys");

const account = (public_key: string | null = null, account_id = "a1") =>
  ({ account_id, display_name: "Juan", login: "juan", public_key });

describe("device key", () => {
  beforeEach(() => {
    store.clear();
    uploads.length = 0;
  });

  it("creates one key even when the page asks several times at once with a stale account", async () => {
    const stale = account(null, "race");
    const keys = await Promise.all([ensureDeviceKey(stale), ensureDeviceKey(stale), ensureDeviceKey(stale)]);
    expect(new Set(keys.map((k) => k.publicKey)).size).toBe(1);
    expect(uploads).toHaveLength(1);
    const again = await ensureDeviceKey(stale);           // still stale: must not replace the key
    expect(again.publicKey).toBe(keys[0].publicKey);
  });

  it("can always open a family it created on this device", async () => {
    const me = account(null, "owner");
    const device = await ensureDeviceKey(me);
    const secret = newSecret();
    const wrapped = await wrapForMember(device.publicKey, secret);
    const later = await ensureDeviceKey(account(null, "owner"));
    const detail = { my_wrapped_key: wrapped } as Parameters<typeof familySecret>[0];
    expect(Array.from(await familySecret(detail, later))).toEqual(Array.from(secret));
  });

  it("keeps an existing device key and re-uploads it if the server copy differs", async () => {
    const first = await ensureDeviceKey(account(null, "kept"));
    uploads.length = 0;
    const { forgetDeviceKey } = await import("./session");
    forgetDeviceKey("kept");
    const second = await ensureDeviceKey(account("someone-else", "kept"));
    expect(second.publicKey).toBe(first.publicKey);
    expect(uploads).toEqual([first.publicKey]);
  });
});
