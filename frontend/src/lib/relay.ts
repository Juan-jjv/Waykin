// Client side of the relay protocol (B5): WS /api/relay/{journey_id}.
// The first frame is `auth`; tokens never go in the URL. Reconnects with exponential backoff
// (0.5 s -> 8 s) and stops for good after 4401 / 4404 / 4409 / 4410.

import { decryptEnvelope, encryptUpdate } from "./crypto";
import type { Envelope, RelayMode, RelayStatus, WalkerUpdate } from "./types";

export const CLOSE = {
  WRONG_KIND: 4400,
  BAD_TOKEN: 4401,
  UNKNOWN: 4404,
  REPLACED: 4409,
  ENDED: 4410,
  TOO_BIG: 4413,
  RATE: 4429,
} as const;
const TERMINAL = new Set<number>([CLOSE.BAD_TOKEN, CLOSE.UNKNOWN, CLOSE.REPLACED, CLOSE.ENDED]);
const BACKOFF_MIN_MS = 500;
const BACKOFF_MAX_MS = 8000;
const MIN_SEND_INTERVAL_MS = 300; // server allows 4 msgs/s

/** Minimal WebSocket surface, so tests can inject a fake. */
export interface WebSocketLike {
  readonly readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: { code: number }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
}
export type WebSocketFactory = (url: string) => WebSocketLike;
const OPEN = 1;

interface Loc {
  host: string;
  protocol: string;
  origin: string;
}
function loc(): Loc {
  const l = (globalThis as { location?: Loc }).location;
  if (!l) throw new Error("location is unavailable");
  return l;
}

export function relayUrl(journeyId: string): string {
  const l = loc();
  const proto = l.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${l.host}/api/relay/${encodeURIComponent(journeyId)}`;
}

export function buildShareLink(journeyId: string, viewerToken: string, keyB64?: string): string {
  const frag = `t=${encodeURIComponent(viewerToken)}` + (keyB64 ? `&k=${encodeURIComponent(keyB64)}` : "");
  return `${loc().origin}/f/${encodeURIComponent(journeyId)}#${frag}`;
}

/** Parses `#t=..&k=..` from a share link fragment (location.hash). */
export function parseShareFragment(hash: string): { token: string | null; key: string | null } {
  const p = new URLSearchParams(hash.replace(/^#/, ""));
  return { token: p.get("t"), key: p.get("k") };
}

export function backoffMs(attempt: number): number {
  return Math.min(BACKOFF_MAX_MS, BACKOFF_MIN_MS * 2 ** attempt);
}

interface BaseOpts {
  journeyId: string;
  relayMode: RelayMode;
  key?: CryptoKey;
  /** Optional: inject a WebSocket implementation (tests) and/or URL. */
  wsFactory?: WebSocketFactory;
  url?: string;
}

abstract class RelayConnection {
  protected ws: WebSocketLike | null = null;
  protected status: RelayStatus | null = null;
  protected stopped = false;
  protected live = false;
  private attempt = 0;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private statusCbs: ((s: RelayStatus) => void)[] = [];

  protected constructor(
    protected readonly o: BaseOpts,
    private readonly role: "walker" | "viewer",
    private readonly token: string,
  ) {
    if (o.relayMode === "e2ee" && !o.key) throw new Error("e2ee relay requires a key");
  }

  onStatus(cb: (s: RelayStatus) => void): void {
    this.statusCbs.push(cb);
    if (this.status) cb(this.status);
  }

  protected setStatus(s: RelayStatus): void {
    if (this.status === s) return;
    this.status = s;
    for (const cb of this.statusCbs) cb(s);
  }

  connect(): void {
    if (this.stopped || this.ws) return;
    this.setStatus(this.attempt === 0 ? "connecting" : "reconnecting");
    const factory: WebSocketFactory = this.o.wsFactory ?? ((u) => new WebSocket(u) as unknown as WebSocketLike);
    const ws = factory(this.o.url ?? relayUrl(this.o.journeyId));
    this.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "auth", role: this.role, token: this.token }));
    ws.onmessage = (ev) => {
      let msg: { type?: string; [k: string]: unknown };
      try {
        msg = JSON.parse(String(ev.data));
      } catch {
        return;
      }
      if (msg.type === "ready") {
        this.attempt = 0;
        this.live = true;
        this.setStatus("live");
        this.onReady();
      } else {
        this.onMessage(msg, String(ev.data));
      }
    };
    ws.onerror = () => {
      /* onclose follows */
    };
    ws.onclose = (ev) => {
      if (this.ws !== ws) return;
      this.ws = null;
      this.live = false;
      if (this.stopped || TERMINAL.has(ev.code)) {
        this.stopped = true;
        this.setStatus("ended");
        this.onTerminal(ev.code);
        return;
      }
      this.setStatus("reconnecting");
      const delay = backoffMs(this.attempt++);
      this.timer = setTimeout(() => {
        this.timer = null;
        this.connect();
      }, delay);
    };
  }

  protected shutdown(code = 1000): void {
    this.stopped = true;
    if (this.timer) clearTimeout(this.timer);
    this.timer = null;
    const ws = this.ws;
    this.ws = null;
    this.live = false;
    if (ws && ws.readyState <= OPEN) ws.close(code);
    this.setStatus("ended");
  }

  protected sendRaw(text: string): boolean {
    if (!this.ws || !this.live || this.ws.readyState !== OPEN) return false;
    this.ws.send(text);
    return true;
  }

  protected onReady(): void {}
  protected abstract onMessage(msg: { type?: string; [k: string]: unknown }, raw: string): void;
  protected onTerminal(_code: number): void {}
}

export class RelayWalker extends RelayConnection {
  private seq: number;
  private pending: string | null = null;
  private lastSentAt = 0;
  private flushTimer: ReturnType<typeof setTimeout> | null = null;
  private readonly walkerToken: string;

  constructor(o: { journeyId: string; walkerToken: string; key?: CryptoKey; relayMode: RelayMode } & Partial<BaseOpts>) {
    super(o, "walker", o.walkerToken);
    this.walkerToken = o.walkerToken;
    this.seq = Date.now() - 1;
  }

  /** Monotonic across reconnects and reloads: Date.now() is the base. */
  private nextSeq(): number {
    this.seq = Math.max(this.seq + 1, Date.now());
    return this.seq;
  }

  async send(u: WalkerUpdate): Promise<void> {
    if (this.stopped) return;
    let text: string;
    if (this.o.relayMode === "e2ee") {
      const env: Envelope = await encryptUpdate(this.o.key!, this.o.journeyId, this.nextSeq(), u);
      text = JSON.stringify({ type: "loc", env });
    } else {
      text = JSON.stringify({ type: "loc", plain: u });
    }
    this.pending = text; // only the latest update matters
    this.flush();
  }

  private flush(): void {
    if (!this.pending || this.flushTimer) return;
    const wait = this.lastSentAt + MIN_SEND_INTERVAL_MS - Date.now();
    if (wait > 0) {
      this.flushTimer = setTimeout(() => {
        this.flushTimer = null;
        this.flush();
      }, wait);
      return;
    }
    if (this.sendRaw(this.pending)) {
      this.pending = null;
      this.lastSentAt = Date.now();
    }
  }

  protected onReady(): void {
    this.flush();
  }

  protected onMessage(): void {
    /* the server sends walkers nothing after ready */
  }

  end(reason: "arrived" | "stopped"): void {
    if (this.stopped) return;
    const sent = this.sendRaw(JSON.stringify({ type: "end", reason }));
    if (!sent) {
      // Not connected: purge through HTTP instead. Fire and forget.
      const f = (globalThis as { fetch?: typeof fetch }).fetch;
      f?.(`/api/journeys/${encodeURIComponent(this.o.journeyId)}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${this.walkerToken}` },
        keepalive: true,
      }).catch(() => undefined);
    }
    if (this.flushTimer) clearTimeout(this.flushTimer);
    this.flushTimer = null;
    this.pending = null;
    this.stopped = true;
    if (!sent) this.shutdown();
    // when sent, the server closes with 4410 and status becomes "ended"
  }
}

export class RelayViewer extends RelayConnection {
  private last = -Infinity;
  private endedFired = false;
  private readonly onUpdate: (u: WalkerUpdate) => void;
  private readonly onEnded: (r: string) => void;

  constructor(
    o: {
      journeyId: string;
      viewerToken: string;
      key?: CryptoKey;
      relayMode: RelayMode;
      onUpdate: (u: WalkerUpdate) => void;
      onEnded: (r: string) => void;
      onStatus?: (s: RelayStatus) => void;
    } & Partial<BaseOpts>,
  ) {
    super(o, "viewer", o.viewerToken);
    this.onUpdate = o.onUpdate;
    this.onEnded = o.onEnded;
    if (o.onStatus) this.onStatus(o.onStatus);
  }

  private fireEnded(reason: string): void {
    if (this.endedFired) return;
    this.endedFired = true;
    this.onEnded(reason);
  }

  protected onMessage(msg: { type?: string; [k: string]: unknown }): void {
    if (msg.type === "ended") {
      this.fireEnded(String(msg.reason ?? "ended"));
      return;
    }
    if (msg.type !== "loc") return;
    if (this.o.relayMode === "e2ee") {
      const env = msg.env as Envelope | undefined;
      if (!env || typeof env.seq !== "number" || env.seq <= this.last) return;
      this.last = env.seq;
      decryptEnvelope(this.o.key!, this.o.journeyId, env).then(
        (u) => {
          if (!this.stopped) this.onUpdate(u);
        },
        () => undefined, // wrong key or tampered: drop
      );
    } else {
      const u = msg.plain as WalkerUpdate | undefined;
      if (!u || typeof u.ts !== "number" || u.ts <= this.last) return;
      this.last = u.ts;
      this.onUpdate(u);
    }
  }

  protected onTerminal(code: number): void {
    if (code === CLOSE.ENDED) this.fireEnded("expired");
    else if (code === CLOSE.UNKNOWN) this.fireEnded("not_found");
    else if (code === CLOSE.BAD_TOKEN) this.fireEnded("invalid_token");
  }

  close(): void {
    this.shutdown(1000);
  }
}
