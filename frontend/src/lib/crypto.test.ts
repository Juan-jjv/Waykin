// @vitest-environment node
import { describe, expect, it } from "vitest";
import { decryptEnvelope, encryptUpdate, exportKeyB64url, generateKey, importKeyB64url } from "./crypto";
import type { WalkerUpdate } from "./types";

const u: WalkerUpdate = { lat: 53.52, lon: -113.52, accuracy_m: 5, ts: 1, status: "walking", eta_min: 9 };

describe("crypto", () => {
  it("round-trips, including the walker-reload path", async () => {
    const k = await generateKey();
    const s = await exportKeyB64url(k);
    expect(s).toHaveLength(43);
    const walkerKey = await importKeyB64url(s, "encrypt");
    const viewerKey = await importKeyB64url(s, "decrypt");
    const env = await encryptUpdate(walkerKey, "j1", 7, u);
    expect(JSON.stringify(env)).not.toContain("53.52");
    expect(await decryptEnvelope(viewerKey, "j1", env)).toEqual(u);
  });

  it("fails with the wrong journey id or seq", async () => {
    const k = await generateKey();
    const env = await encryptUpdate(k, "j1", 7, u);
    await expect(decryptEnvelope(k, "j2", env)).rejects.toBeTruthy();
    await expect(decryptEnvelope(k, "j1", { ...env, seq: 8 })).rejects.toBeTruthy();
  });

  it("uses a fresh IV every time", async () => {
    const k = await generateKey();
    const ivs = new Set<string>();
    for (let i = 0; i < 1000; i++) ivs.add((await encryptUpdate(k, "j", i, u)).iv);
    expect(ivs.size).toBe(1000);
  });
});
