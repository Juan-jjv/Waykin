// End-to-end encryption for the family relay (B5).
// AES-GCM-256, key generated in the walker's browser, fresh random 12-byte IV per message,
// AAD = UTF-8 of `waykin:v1:${journeyId}:${seq}`, plaintext = JSON.stringify(WalkerUpdate).
// The key travels only in the share link's #fragment, so the server never receives it.

import type { Envelope, WalkerUpdate } from "./types";

const ALG = "AES-GCM";
const IV_BYTES = 12;
const KEY_B64_LEN = 43; // 32 bytes, base64url, no padding

const enc = new TextEncoder();
const dec = new TextDecoder();

function subtle(): SubtleCrypto {
  const c = globalThis.crypto;
  if (!c?.subtle) throw new Error("WebCrypto is unavailable (a secure context, https or localhost, is required)");
  return c.subtle;
}

export function b64urlEncode(bytes: Uint8Array): string {
  let s = "";
  for (let i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64urlDecode(s: string) {
  if (!/^[A-Za-z0-9_-]*$/.test(s)) throw new Error("invalid base64url");
  const b64 = s.replace(/-/g, "+").replace(/_/g, "/") + "=".repeat((4 - (s.length % 4)) % 4);
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export function aad(journeyId: string, seq: number) {
  return enc.encode(`waykin:v1:${journeyId}:${seq}`);
}

export async function generateKey(): Promise<CryptoKey> {
  return subtle().generateKey({ name: ALG, length: 256 }, true, ["encrypt", "decrypt"]);
}

export async function exportKeyB64url(k: CryptoKey): Promise<string> {
  const raw = new Uint8Array(await subtle().exportKey("raw", k));
  return b64urlEncode(raw);
}

/** Imports a viewer key from the share link. Decrypt-only. */
export async function importKeyB64url(s: string): Promise<CryptoKey> {
  if (s.length !== KEY_B64_LEN) throw new Error("invalid key");
  const raw = b64urlDecode(s);
  if (raw.length !== 32) throw new Error("invalid key");
  return subtle().importKey("raw", raw, { name: ALG }, false, ["decrypt"]);
}

export async function encryptUpdate(
  k: CryptoKey,
  journeyId: string,
  seq: number,
  u: WalkerUpdate,
): Promise<Envelope> {
  if (!Number.isInteger(seq) || seq < 0 || seq > 2 ** 53 - 1) throw new Error("seq must be a non-negative integer");
  const iv = globalThis.crypto.getRandomValues(new Uint8Array(IV_BYTES));
  const ct = await subtle().encrypt(
    { name: ALG, iv, additionalData: aad(journeyId, seq) },
    k,
    enc.encode(JSON.stringify(u)),
  );
  return { v: 1, seq, iv: b64urlEncode(iv), ct: b64urlEncode(new Uint8Array(ct)) };
}

export async function decryptEnvelope(k: CryptoKey, journeyId: string, e: Envelope): Promise<WalkerUpdate> {
  if (e.v !== 1) throw new Error("unsupported envelope version");
  const iv = b64urlDecode(e.iv);
  if (iv.length !== IV_BYTES) throw new Error("invalid iv");
  const pt = await subtle().decrypt(
    { name: ALG, iv, additionalData: aad(journeyId, e.seq) },
    k,
    b64urlDecode(e.ct),
  );
  return JSON.parse(dec.decode(pt)) as WalkerUpdate;
}
