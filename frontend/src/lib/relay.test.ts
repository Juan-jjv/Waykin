// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { exportKeyB64url, generateKey, importKeyB64url } from "./crypto";
import { backoffMs, buildShareLink, parseShareFragment, RelayViewer, RelayWalker, type WebSocketLike } from "./relay";
import type { RelayStatus, WalkerUpdate } from "./types";

class FakeWS implements WebSocketLike {
  static all: FakeWS[] = [];
  readyState = 0;
  sent: string[] = [];
  onopen: ((ev: unknown) => void) | null = null;
  onmessage: ((ev: { data: unknown }) => void) | null = null;
  onclose: ((ev: { code: number }) => void) | null = null;
  onerror: ((ev: unknown) => void) | null = null;
  constructor(public url: string) {
    FakeWS.all.push(this);
  }
  send(d: string) {
    this.sent.push(d);
  }
  close(code = 1000) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
  open() {
    this.readyState = 1;
    this.onopen?.({});
  }
  recv(m: unknown) {
    this.onmessage?.({ data: typeof m === "string" ? m : JSON.stringify(m) });
  }
  serverClose(code: number) {
    this.readyState = 3;
    this.onclose?.({ code });
  }
}
const factory = (u: string) => new FakeWS(u);
const ready = { type: "ready", relay_mode: "e2ee", expires_at: "2026-11-07T20:00:00Z" };
const upd: WalkerUpdate = { lat: 53.52, lon: -113.51, accuracy_m: 5, ts: 10, status: "walking", eta_min: 5 };
const flush = () => new Promise((r) => setTimeout(r, 0));

beforeEach(() => {
  FakeWS.all = [];
  vi.stubGlobal("location", { protocol: "https:", host: "waykin.test", origin: "https://waykin.test" });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("share link", () => {
  it("puts token and key in the fragment", () => {
    const link = buildShareLink("j1", "tok", "k".repeat(43));
    expect(link).toBe(`https://waykin.test/f/j1#t=tok&k=${"k".repeat(43)}`);
    const u = new URL(link);
    expect(u.search).toBe("");
    expect(parseShareFragment(u.hash)).toEqual({ token: "tok", key: "k".repeat(43) });
  });
});

describe("backoff", () => {
  it("goes from 0.5 s to 8 s", () => {
    expect([0, 1, 2, 3, 4, 5, 9].map(backoffMs)).toEqual([500, 1000, 2000, 4000, 8000, 8000, 8000]);
  });
});

describe("RelayWalker + RelayViewer", () => {
  it("authenticates first, encrypts, and the viewer decrypts", async () => {
    const key = await generateKey();
    const vkey = await importKeyB64url(await exportKeyB64url(key));
    const w = new RelayWalker({ journeyId: "j1", walkerToken: "wt", key, relayMode: "e2ee", wsFactory: factory });
    const st: RelayStatus[] = [];
    w.onStatus((s) => st.push(s));
    w.connect();
    const ws = FakeWS.all[0];
    expect(ws.url).toBe("wss://waykin.test/api/relay/j1");
    ws.open();
    expect(JSON.parse(ws.sent[0])).toEqual({ type: "auth", role: "walker", token: "wt" });
    ws.recv(ready);
    expect(st).toEqual(["connecting", "live"]);
    await w.send(upd);
    const msg = JSON.parse(ws.sent[1]);
    expect(msg.type).toBe("loc");
    expect(Object.keys(msg)).toEqual(["type", "env"]);
    expect(ws.sent[1]).not.toContain("lat");

    const got: WalkerUpdate[] = [];
    const v = new RelayViewer({
      journeyId: "j1", viewerToken: "vt", key: vkey, relayMode: "e2ee",
      onUpdate: (u) => got.push(u), onEnded: () => undefined, wsFactory: factory,
    });
    v.connect();
    const vws = FakeWS.all[1];
    vws.open();
    vws.recv(ready);
    vws.recv(ws.sent[1]);
    vws.recv(ws.sent[1]); // duplicate seq is dropped
    await flush();
    await flush();
    expect(got).toEqual([upd]);
  });

  it("keeps seq monotonic across reconnects and backs off", async () => {
    vi.useFakeTimers();
    const key = await generateKey();
    const w = new RelayWalker({ journeyId: "j1", walkerToken: "wt", key, relayMode: "e2ee", wsFactory: factory });
    const st: RelayStatus[] = [];
    w.onStatus((s) => st.push(s));
    w.connect();
    FakeWS.all[0].open();
    FakeWS.all[0].recv(ready);
    await w.send(upd);
    const seq1 = JSON.parse(FakeWS.all[0].sent[1]).env.seq;
    FakeWS.all[0].serverClose(1006);
    expect(st.at(-1)).toBe("reconnecting");
    vi.advanceTimersByTime(499);
    expect(FakeWS.all).toHaveLength(1);
    vi.advanceTimersByTime(1);
    expect(FakeWS.all).toHaveLength(2);
    FakeWS.all[1].open();
    FakeWS.all[1].recv(ready);
    vi.advanceTimersByTime(1000);
    await w.send(upd);
    const seq2 = JSON.parse(FakeWS.all[1].sent.at(-1)!).env.seq;
    expect(seq2).toBeGreaterThan(seq1);
  });

  it("stops reconnecting after 4401, 4404, 4409 and 4410", () => {
    vi.useFakeTimers();
    for (const code of [4401, 4404, 4409, 4410]) {
      FakeWS.all = [];
      const ended: string[] = [];
      const v = new RelayViewer({
        journeyId: "j", viewerToken: "vt", relayMode: "plaintext",
        onUpdate: () => undefined, onEnded: (r) => ended.push(r), wsFactory: factory,
      });
      const st: RelayStatus[] = [];
      v.onStatus((s) => st.push(s));
      v.connect();
      FakeWS.all[0].open();
      FakeWS.all[0].serverClose(code);
      vi.advanceTimersByTime(60_000);
      expect(FakeWS.all).toHaveLength(1);
      expect(st.at(-1)).toBe("ended");
    }
  });

  it("viewer fires onEnded once on `ended` then 4410", () => {
    const ended: string[] = [];
    const v = new RelayViewer({
      journeyId: "j", viewerToken: "vt", relayMode: "plaintext",
      onUpdate: () => undefined, onEnded: (r) => ended.push(r), wsFactory: factory,
    });
    v.connect();
    FakeWS.all[0].open();
    FakeWS.all[0].recv({ ...ready, relay_mode: "plaintext" });
    FakeWS.all[0].recv({ type: "ended", reason: "arrived" });
    FakeWS.all[0].serverClose(4410);
    expect(ended).toEqual(["arrived"]);
  });

  it("plaintext viewer drops older updates", () => {
    const got: number[] = [];
    const v = new RelayViewer({
      journeyId: "j", viewerToken: "vt", relayMode: "plaintext",
      onUpdate: (u) => got.push(u.ts), onEnded: () => undefined, wsFactory: factory,
    });
    v.connect();
    FakeWS.all[0].open();
    FakeWS.all[0].recv(ready);
    for (const ts of [5, 4, 6, 6]) FakeWS.all[0].recv({ type: "loc", plain: { ...upd, ts } });
    expect(got).toEqual([5, 6]);
  });

  it("walker end() sends end, or DELETEs when offline", () => {
    const w = new RelayWalker({ journeyId: "j", walkerToken: "wt", relayMode: "plaintext", wsFactory: factory });
    w.connect();
    FakeWS.all[0].open();
    FakeWS.all[0].recv(ready);
    w.end("arrived");
    expect(JSON.parse(FakeWS.all[0].sent.at(-1)!)).toEqual({ type: "end", reason: "arrived" });

    const fetchMock = vi.fn(() => Promise.resolve(new Response(null, { status: 204 })));
    vi.stubGlobal("fetch", fetchMock);
    const w2 = new RelayWalker({ journeyId: "j2", walkerToken: "wt2", relayMode: "plaintext", wsFactory: factory });
    w2.end("stopped");
    expect(fetchMock).toHaveBeenCalledWith("/api/journeys/j2", expect.objectContaining({ method: "DELETE" }));
  });

  it("requires a key in e2ee mode", () => {
    expect(() => new RelayWalker({ journeyId: "j", walkerToken: "t", relayMode: "e2ee" })).toThrow();
  });
});
