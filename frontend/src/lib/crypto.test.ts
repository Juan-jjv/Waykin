// @vitest-environment node
import { describe, expect, it } from "vitest";
import { b64urlDecode, decryptEnvelope, encryptUpdate, exportKeyB64url, generateKey, importKeyB64url } from "./crypto";
import type { WalkerUpdate } from "./types";

const u: WalkerUpdate = { lat: 53.52, lon: -113.51, accuracy_m: 5, ts: 1, status: "walking", eta_min: 9 };

describe("crypto", () => {
  it("round-trips an update", async () => {
    const k = await generateKey();
    const e = await encryptUpdate(k, "jid", 42, u);
    expect(e.v).toBe(1);
    expect(e.seq).toBe(42);
    expect(e.iv).toMatch(/^[A-Za-z0-9_-]{16}$/);
    expect(e.ct).toMatch(/^[A-Za-z0-9_-]+$/);
    expect(JSON.stringify(e)).not.toContain("lat");
    expect(await decryptEnvelope(k, "jid", e)).toEqual(u);
  });

  it("viewer key imported from the link decrypts", async () => {
    const k = await generateKey();
    const viewer = await importKeyB64url(await exportKeyB64url(k));
    expect(viewer.usages).toEqual(["decrypt"]);
    const e = await encryptUpdate(k, "jid", 1, u);
    expect(await decryptEnvelope(viewer, "jid", e)).toEqual(u);
  });

  it("fails with the wrong journey id or seq", async () => {
    const k = await generateKey();
    const e = await encryptUpdate(k, "jid", 7, u);
    await expect(decryptEnvelope(k, "other", e)).rejects.toBeTruthy();
    await expect(decryptEnvelope(k, "jid", { ...e, seq: 8 })).rejects.toBeTruthy();
  });

  it("fails with a different key", async () => {
    const e = await encryptUpdate(await generateKey(), "jid", 1, u);
    await expect(decryptEnvelope(await generateKey(), "jid", e)).rejects.toBeTruthy();
  });

  it("uses 1000 unique IVs", async () => {
    const k = await generateKey();
    const ivs = new Set<string>();
    for (let i = 0; i < 1000; i++) ivs.add((await encryptUpdate(k, "jid", i, u)).iv);
    expect(ivs.size).toBe(1000);
    expect(b64urlDecode([...ivs][0]).length).toBe(12);
  });

  it("exports a 43-character key", async () => {
    const s = await exportKeyB64url(await generateKey());
    expect(s).toHaveLength(43);
    expect(s).toMatch(/^[A-Za-z0-9_-]{43}$/);
    await expect(importKeyB64url(s.slice(1))).rejects.toBeTruthy();
  });
});
