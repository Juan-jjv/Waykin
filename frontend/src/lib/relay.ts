// Owner: A4. Relay clients (spec B5 protocol). The token goes in the first frame, never in the URL.
import { decryptEnvelope, encryptUpdate } from "./crypto";
import type { Envelope, RelayMode, RelayStatus, WalkerUpdate } from "./types";

const FATAL = new Set([4401, 4404, 4410]);

export function buildShareLink(journeyId: string, viewerToken: string, keyB64?: string): string {
  const frag = new URLSearchParams({ t: viewerToken });
  if (keyB64) frag.set("k", keyB64);
  return `${location.origin}/f/${encodeURIComponent(journeyId)}#${frag.toString()}`;
}

function relayUrl(journeyId: string): string {
  const proto = location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${location.host}/api/relay/${encodeURIComponent(journeyId)}`;
}

abstract class RelayBase {
  protected ws: WebSocket | null = null;
  protected backoff = 500;
  protected closedByUs = false;
  protected statusCb: ((s: RelayStatus) => void) | undefined;

  constructor(protected journeyId: string, private token: string, private role: "walker" | "viewer") {}

  protected setStatus(s: RelayStatus) {
    this.statusCb?.(s);
  }

  connect(): void {
    this.closedByUs = false;
    this.setStatus("connecting");
    const ws = new WebSocket(relayUrl(this.journeyId));
    this.ws = ws;
    ws.onopen = () => ws.send(JSON.stringify({ type: "auth", role: this.role, token: this.token }));
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string);
      if (msg.type === "ready") {
        this.backoff = 500;
        this.setStatus("live");
      }
      this.onMessage(msg);
    };
    ws.onclose = (ev) => {
      if (this.closedByUs || FATAL.has(ev.code)) {
        this.setStatus("ended");
        if (FATAL.has(ev.code)) this.onFatal(ev.code);
        return;
      }
      this.setStatus("reconnecting");
      setTimeout(() => this.connect(), this.backoff);
      this.backoff = Math.min(this.backoff * 2, 8000);
    };
  }

  protected sendRaw(obj: unknown): boolean {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(obj));
      return true;
    }
    return false;
  }

  protected shut() {
    this.closedByUs = true;
    this.ws?.close();
  }

  protected abstract onMessage(msg: { type: string; [k: string]: unknown }): void;
  protected onFatal(_code: number): void {}
}

export class RelayWalker extends RelayBase {
  private seq = Date.now(); // monotonic across reconnects
  private key?: CryptoKey;
  private mode: RelayMode;

  constructor(o: { journeyId: string; walkerToken: string; key?: CryptoKey; relayMode: RelayMode }) {
    super(o.journeyId, o.walkerToken, "walker");
    this.key = o.key;
    this.mode = o.relayMode;
  }

  onStatus(cb: (s: RelayStatus) => void): void {
    this.statusCb = cb;
  }

  async send(u: WalkerUpdate): Promise<void> {
    if (this.mode === "e2ee") {
      if (!this.key) throw new Error("e2ee relay needs a key");
      const env = await encryptUpdate(this.key, this.journeyId, ++this.seq, u);
      this.sendRaw({ type: "loc", env });
    } else {
      this.sendRaw({ type: "loc", plain: u });
    }
  }

  end(reason: "arrived" | "stopped"): void {
    this.sendRaw({ type: "end", reason });
    this.shut();
  }

  protected onMessage(): void {}
}

export class RelayViewer extends RelayBase {
  private lastSeq = -1;
  private key?: CryptoKey;
  private mode: RelayMode;
  private onUpdate: (u: WalkerUpdate) => void;
  private onEnded: (r: string) => void;

  constructor(o: {
    journeyId: string; viewerToken: string; key?: CryptoKey; relayMode: RelayMode;
    onUpdate: (u: WalkerUpdate) => void; onEnded: (r: string) => void; onStatus?: (s: RelayStatus) => void;
  }) {
    super(o.journeyId, o.viewerToken, "viewer");
    this.key = o.key;
    this.mode = o.relayMode;
    this.onUpdate = o.onUpdate;
    this.onEnded = o.onEnded;
    this.statusCb = o.onStatus;
  }

  close(): void {
    this.shut();
  }

  protected onMessage(msg: { type: string; [k: string]: unknown }): void {
    if (msg.type === "ended") {
      this.onEnded(String(msg.reason));
      return;
    }
    if (msg.type !== "loc") return;
    if (this.mode === "e2ee" && msg.env) {
      const env = msg.env as Envelope;
      if (env.seq <= this.lastSeq || !this.key) return;
      this.lastSeq = env.seq;
      decryptEnvelope(this.key, this.journeyId, env).then(this.onUpdate).catch(() => undefined);
    } else if (this.mode === "plaintext" && msg.plain) {
      this.onUpdate(msg.plain as WalkerUpdate);
    }
  }

  protected onFatal(code: number): void {
    if (code === 4410 || code === 4404) this.onEnded(code === 4410 ? "expired" : "not_found");
  }
}
