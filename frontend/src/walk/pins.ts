// The two stop PINs, kept only on this device as salted SHA-256 hashes. The alert PIN ends sharing exactly like
// the normal one on screen, but the final encrypted update carries a "duress" alert to the family.

const KEY = "waykin:pins";
type Stored = { normal: string; alert: string };

export const validPin = (pin: string) => /^\d{4,8}$/.test(pin);

async function digest(pin: string): Promise<string> {
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(`waykin-pin:v1:${pin}`));
  return Array.from(new Uint8Array(buf), (b) => b.toString(16).padStart(2, "0")).join("");
}

function read(): Stored | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Stored) : null;
  } catch {
    return null;
  }
}

export function hasPins(): boolean {
  return read() !== null;
}

export async function savePins(normal: string, alert: string): Promise<boolean> {
  if (!validPin(normal) || !validPin(alert) || normal === alert) return false;
  try {
    localStorage.setItem(KEY, JSON.stringify({ normal: await digest(normal), alert: await digest(alert) }));
    return true;
  } catch {
    return false;
  }
}

export function clearPins(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    /* storage blocked */
  }
}

export async function checkPin(pin: string): Promise<"normal" | "alert" | null> {
  const s = read();
  if (!s) return null;
  const h = await digest(pin);
  return h === s.normal ? "normal" : h === s.alert ? "alert" : null;
}
