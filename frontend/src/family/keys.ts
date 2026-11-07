// Family key cryptography (WebCrypto only). The server stores wrapped keys it cannot open.
//
// * Each signed-in device has an ECDH P-256 key pair. The private key never leaves the device (non-extractable,
//   kept in IndexedDB); the public key is uploaded so family members can wrap keys for it.
// * A family has one 256-bit secret. It is wrapped for each member: ephemeral ECDH with the member's public key,
//   HKDF-SHA-256, then AES-GCM. Format: "v1.<ephemeral public>.<iv>.<ciphertext>" (base64url).
// * Each family walk has its own AES-GCM journey key, wrapped with the family secret ("v1.<iv>.<ciphertext>"), so
//   every member can open it. The walk itself uses the normal relay encryption from lib/crypto.
import { b64urlDecode, b64urlEncode, importKeyB64url } from "../lib/crypto";

const enc = new TextEncoder();
const MEMBER_INFO = enc.encode("waykin:family-key-wrap:v1");

/** Copy into a fresh ArrayBuffer-backed array: WebCrypto's types reject views over SharedArrayBuffer. */
const bytes = (b: Uint8Array): Uint8Array => new Uint8Array(b);

export function newSecret(): Uint8Array {
  return crypto.getRandomValues(new Uint8Array(32));
}

export async function newDeviceKeyPair(): Promise<CryptoKeyPair> {
  // extractable=false applies to the private key; an ECDH public key is always exportable.
  return crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"]) as Promise<CryptoKeyPair>;
}

export async function exportPublicKey(key: CryptoKey): Promise<string> {
  return b64urlEncode(new Uint8Array(await crypto.subtle.exportKey("raw", key)));
}

async function importPublicKey(b64: string): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", bytes(b64urlDecode(b64)), { name: "ECDH", namedCurve: "P-256" }, true, []);
}

async function sharedKey(privateKey: CryptoKey, publicKey: CryptoKey): Promise<CryptoKey> {
  const bits = await crypto.subtle.deriveBits({ name: "ECDH", public: publicKey }, privateKey, 256);
  const hkdf = await crypto.subtle.importKey("raw", bits, "HKDF", false, ["deriveKey"]);
  return crypto.subtle.deriveKey(
    { name: "HKDF", hash: "SHA-256", salt: new Uint8Array(32), info: MEMBER_INFO },
    hkdf, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"],
  );
}

/** Wrap a family secret so that only the holder of `memberPublicKey`'s private key can open it. */
export async function wrapForMember(memberPublicKey: string, secret: Uint8Array): Promise<string> {
  const ephemeral = (await crypto.subtle.generateKey({ name: "ECDH", namedCurve: "P-256" }, false, ["deriveBits"])) as CryptoKeyPair;
  const key = await sharedKey(ephemeral.privateKey, await importPublicKey(memberPublicKey));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv }, key, bytes(secret));
  return ["v1", await exportPublicKey(ephemeral.publicKey), b64urlEncode(iv), b64urlEncode(new Uint8Array(ct))].join(".");
}

export async function unwrapForDevice(wrapped: string, devicePrivateKey: CryptoKey): Promise<Uint8Array> {
  const [v, epk, iv, ct] = wrapped.split(".");
  if (v !== "v1" || !epk || !iv || !ct) throw new Error("unknown key format");
  const key = await sharedKey(devicePrivateKey, await importPublicKey(epk));
  return new Uint8Array(await crypto.subtle.decrypt({ name: "AES-GCM", iv: bytes(b64urlDecode(iv)) }, key, bytes(b64urlDecode(ct))));
}

const journeyAad = (familyId: string, keyVersion: number) => enc.encode(`waykin:journey-key:v1:${familyId}:${keyVersion}`);

async function familyAes(secret: Uint8Array, usage: KeyUsage): Promise<CryptoKey> {
  return crypto.subtle.importKey("raw", bytes(secret), { name: "AES-GCM" }, false, [usage]);
}

export async function wrapJourneyKey(secret: Uint8Array, journeyKeyB64: string, familyId: string, keyVersion: number): Promise<string> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: journeyAad(familyId, keyVersion) },
    await familyAes(secret, "encrypt"), bytes(b64urlDecode(journeyKeyB64)));
  return ["v1", b64urlEncode(iv), b64urlEncode(new Uint8Array(ct))].join(".");
}

/** Opens a family walk's key and imports it for decrypting the walker's updates. */
export async function openJourneyKey(secret: Uint8Array, wrapped: string, familyId: string, keyVersion: number): Promise<CryptoKey> {
  const [v, iv, ct] = wrapped.split(".");
  if (v !== "v1" || !iv || !ct) throw new Error("unknown key format");
  const raw = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: bytes(b64urlDecode(iv)), additionalData: journeyAad(familyId, keyVersion) },
    await familyAes(secret, "decrypt"), bytes(b64urlDecode(ct)));
  return importKeyB64url(b64urlEncode(new Uint8Array(raw)), "decrypt");
}

/** Invite links carry the token and the family secret in the #fragment, which browsers never send to the server. */
export function buildInviteLink(origin: string, familyId: string, token: string, secret: Uint8Array, keyVersion: number): string {
  const frag = new URLSearchParams({ i: token, k: b64urlEncode(secret), v: String(keyVersion) });
  return `${origin}/join/${encodeURIComponent(familyId)}#${frag.toString()}`;
}

export function parseInviteFragment(hash: string): { token: string; secret: Uint8Array; keyVersion: number } | null {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  const token = p.get("i");
  const k = p.get("k");
  const v = Number(p.get("v"));
  if (!token || !k || !Number.isInteger(v) || v < 1) return null;
  const secret = bytes(b64urlDecode(k));
  return secret.length === 32 ? { token, secret, keyVersion: v } : null;
}
