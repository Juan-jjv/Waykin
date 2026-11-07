import { describe, expect, it } from "vitest";
import { exportKeyB64url, generateKey, decryptEnvelope, encryptUpdate } from "../lib/crypto";
import {
  buildInviteLink, exportPublicKey, newDeviceKeyPair, newSecret, openJourneyKey, parseInviteFragment, unwrapForDevice,
  wrapForMember, wrapJourneyKey,
} from "./keys";

describe("family keys", () => {
  it("wraps a family secret that only the intended member can open", async () => {
    const alex = await newDeviceKeyPair();
    const kim = await newDeviceKeyPair();
    const secret = newSecret();
    const wrapped = await wrapForMember(await exportPublicKey(alex.publicKey), secret);
    expect(wrapped.startsWith("v1.")).toBe(true);
    expect(Array.from(await unwrapForDevice(wrapped, alex.privateKey))).toEqual(Array.from(secret));
    await expect(unwrapForDevice(wrapped, kim.privateKey)).rejects.toBeTruthy();
  });

  it("lets every member open a family walk's key and read the walker's updates", async () => {
    const secret = newSecret();
    const walkKey = await generateKey();
    const wrapped = await wrapJourneyKey(secret, await exportKeyB64url(walkKey), "fam1", 3);
    const opened = await openJourneyKey(secret, wrapped, "fam1", 3);
    const update = { lat: 53.52, lon: -113.52, accuracy_m: 5, ts: 1, status: "walking" as const, eta_min: 4 };
    const env = await encryptUpdate(walkKey, "j1", 7, update);
    expect(await decryptEnvelope(opened, "j1", env)).toEqual(update);
    await expect(openJourneyKey(secret, wrapped, "fam1", 4)).rejects.toBeTruthy();       // bound to the key version
    await expect(openJourneyKey(newSecret(), wrapped, "fam1", 3)).rejects.toBeTruthy();  // and to the family secret
  });

  it("keeps the invite token and secret in the fragment only", () => {
    const secret = newSecret();
    const link = buildInviteLink("https://waykin.test", "fam 1", "tok123456789", secret, 2);
    const url = new URL(link);
    expect(url.pathname).toBe("/join/fam%201");
    expect(url.search).toBe("");
    const parsed = parseInviteFragment(url.hash);
    expect(parsed?.token).toBe("tok123456789");
    expect(parsed?.keyVersion).toBe(2);
    expect(Array.from(parsed!.secret)).toEqual(Array.from(secret));
    expect(parseInviteFragment("#i=x")).toBeNull();
  });
});
