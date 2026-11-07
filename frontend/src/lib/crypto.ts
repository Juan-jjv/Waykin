// Owner: A4. End-to-end encryption of walker updates (spec B5): AES-GCM 256, fresh 12-byte IV per message,
// AAD = "waykin:v1:{journeyId}:{seq}". The key is made in the walker's browser and travels only in the
// share link's #fragment, which browsers never send to the server.
import type { Envelope, WalkerUpdate } from "./types";

const enc = new TextEncoder();
const dec = new TextDecoder();

export function b64urlEncode(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function b64urlDecode(s: string): Uint8Array {
  const pad = s.length % 4 === 0 ? "" : "=".repeat(4 - (s.length % 4));
  const bin = atob(s.replace(/-/g, "+").replace(/_/g, "/") + pad);
  return Uint8Array.from(bin, (c) => c.charCodeAt(0));
}

const aad = (journeyId: string, seq: number) => enc.encode(`waykin:v1:${journeyId}:${seq}`);

export async function generateKey(): Promise<CryptoKey> {
  return crypto.subtle.generateKey({ name: "AES-GCM", length: 256 }, true, ["encrypt", "decrypt"]);
}

export async function exportKeyB64url(k: CryptoKey): Promise<string> {
  return b64urlEncode(new Uint8Array(await crypto.subtle.exportKey("raw", k)));
}

/** Walker re-imports with "encrypt" after a reload; viewers use "decrypt". */
export async function importKeyB64url(s: string, usage: "encrypt" | "decrypt"): Promise<CryptoKey> {
  const raw = b64urlDecode(s);
  if (raw.length !== 32) throw new Error("invalid key");
  return crypto.subtle.importKey("raw", raw, { name: "AES-GCM" }, false, [usage]);
}

export async function encryptUpdate(k: CryptoKey, journeyId: string, seq: number, u: WalkerUpdate): Promise<Envelope> {
  const iv = crypto.getRandomValues(new Uint8Array(12));
  const ct = await crypto.subtle.encrypt({ name: "AES-GCM", iv, additionalData: aad(journeyId, seq) }, k,
    enc.encode(JSON.stringify(u)));
  return { v: 1, seq, iv: b64urlEncode(iv), ct: b64urlEncode(new Uint8Array(ct)) };
}

export async function decryptEnvelope(k: CryptoKey, journeyId: string, e: Envelope): Promise<WalkerUpdate> {
  const pt = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: b64urlDecode(e.iv), additionalData: aad(journeyId, e.seq) }, k, b64urlDecode(e.ct));
  return JSON.parse(dec.decode(pt)) as WalkerUpdate;
}
