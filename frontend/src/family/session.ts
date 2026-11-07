// Ties the family keys to the signed-in account: device key, family secrets, invites, key rotation, family walks.
import type { AccountOut, FamilyDetail, FamilyJourney } from "../api/types";
import { exportKeyB64url, generateKey } from "../lib/crypto";
import { accountApi } from "./api";
import { idb, KEYS } from "./idb";
import {
  buildInviteLink, exportPublicKey, newDeviceKeyPair, newSecret, openJourneyKey, unwrapForDevice, wrapForMember,
  wrapJourneyKey,
} from "./keys";

type DeviceKey = { privateKey: CryptoKey; publicKey: string };

/** This device's key pair for the account. Creates and uploads one if missing; a new device replaces the old key. */
export async function ensureDeviceKey(account: AccountOut): Promise<DeviceKey> {
  const id = `device:${account.account_id}`;
  const stored = await idb.get<DeviceKey>(KEYS, id);
  if (stored && stored.publicKey === account.public_key) return stored;
  const pair = await newDeviceKeyPair();
  const fresh = { privateKey: pair.privateKey, publicKey: await exportPublicKey(pair.publicKey) };
  await idb.put(KEYS, fresh, id);
  await accountApi.setPublicKey(fresh.publicKey);
  return fresh;
}

export class NoFamilyKey extends Error {}

/** This member's copy of the family secret. Fails when the key was wrapped for another device. */
export async function familySecret(detail: FamilyDetail, device: DeviceKey): Promise<Uint8Array> {
  if (!detail.my_wrapped_key) throw new NoFamilyKey("no key for this device");
  try {
    return await unwrapForDevice(detail.my_wrapped_key, device.privateKey);
  } catch {
    throw new NoFamilyKey("this device can't open the family key");
  }
}

export async function createFamily(name: string, device: DeviceKey): Promise<FamilyDetail> {
  return accountApi.createFamily(name, await wrapForMember(device.publicKey, newSecret()));
}

export async function inviteLink(detail: FamilyDetail, device: DeviceKey): Promise<string> {
  const secret = await familySecret(detail, device);
  const invite = await accountApi.createInvite(detail.family_id);
  return buildInviteLink(location.origin, detail.family_id, invite.invite_token, secret, detail.key_version);
}

export async function joinFamily(fid: string, token: string, secret: Uint8Array, keyVersion: number, device: DeviceKey) {
  return accountApi.join(fid, token, await wrapForMember(device.publicKey, secret), keyVersion);
}

/** Owner removes someone, then replaces the family secret so the removed person can't read new walks. */
export async function removeAndRotate(detail: FamilyDetail, accountId: string): Promise<void> {
  await accountApi.removeMember(detail.family_id, accountId);
  const after = await accountApi.family(detail.family_id);
  const secret = newSecret();
  const wrapped: Record<string, string> = {};
  for (const m of after.members) {
    if (!m.public_key) continue;
    wrapped[m.account_id] = await wrapForMember(m.public_key, secret);
  }
  await accountApi.rotateKeys(after.family_id, after.key_version + 1, wrapped);
}

/** Starts a walk the family can follow. Returns the relay credentials and this walk's key. */
export async function startFamilyWalk(detail: FamilyDetail, device: DeviceKey) {
  const secret = await familySecret(detail, device);
  const walkKey = await generateKey();
  const keyB64 = await exportKeyB64url(walkKey);
  const wrapped = await wrapJourneyKey(secret, keyB64, detail.family_id, detail.key_version);
  const created = await accountApi.startFamilyJourney(detail.family_id, wrapped, detail.key_version);
  return { created, key: walkKey, keyB64 };
}

/** The key for following a family member's walk. */
export async function followKey(detail: FamilyDetail, journey: FamilyJourney, device: DeviceKey): Promise<CryptoKey> {
  const secret = await familySecret(detail, device);
  return openJourneyKey(secret, journey.wrapped_journey_key, detail.family_id, journey.key_version);
}
