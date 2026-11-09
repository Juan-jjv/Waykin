import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import { useMeta } from "../api/hooks";
import type { AlertKind, FamilyDetail, Hazard, LatLon, RouteOption, TravelMode, WalkerUpdate } from "../api/types";
import { BannerStack, useBanners } from "../components/AlertCenter";
import { MapView } from "../components/MapView";
import { NavBar } from "../components/NavBar";
import { TrackLayer } from "../components/TrackLayer";
import { driveText, walkText } from "../copy/familyStrings";
import { accountApi, useAccount, useFamilies } from "../family/api";
import { logActivity } from "../family/history";
import { ensureDeviceKey, startFamilyWalk } from "../family/session";
import { exportKeyB64url, generateKey } from "../lib/crypto";
import { buildShareLink, RelayWalker } from "../lib/relay";
import type { RelayStatus } from "../lib/types";
import { SimGeo, type GeoPoint } from "../geo/geo";
import { AlertMonitor, remainingMetres } from "../walk/alerts";
import { checkPin, hasPins } from "../walk/pins";

const DRAFT_KEY = "waykin:route:draft";
const WALK_M_PER_MIN = 80;

/** The route's own average pace, so ETAs and the simulator suit walking or driving. */
function paceOf(route: RouteOption): number {
  return route.minutes > 0 && route.distance_m > 0 ? route.distance_m / route.minutes : WALK_M_PER_MIN;
}
const ROUTE_RESEND_EVERY = 10;

type Draft = {
  route: RouteOption;
  destination: LatLon;
  originLabel?: string | null;
  destinationLabel?: string | null;
  mode?: TravelMode;
};
type Share = { kind: "family"; fid: string } | { kind: "link" } | { kind: "nobody" };
type Phase = "setup" | "starting" | "walking" | "ended";

function readDraft(): Draft | null {
  try {
    const raw = sessionStorage.getItem(DRAFT_KEY);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

export function WalkPage() {
  const draft = useRef(readDraft()).current;
  const text = draft?.mode === "drive" ? driveText : walkText;
  const meta = useMeta().data;
  const account = useAccount().data ?? null;
  const families = useFamilies(Boolean(account)).data ?? [];
  const { banners, push, dismiss } = useBanners();
  const navigate = useNavigate();

  const [share, setShare] = useState<Share>({ kind: "link" });
  const [source, setSource] = useState<"gps" | "sim">("sim");
  const [phase, setPhase] = useState<Phase>("setup");
  const [error, setError] = useState<string | null>(null);
  const [route, setRoute] = useState<RouteOption | null>(draft?.route ?? null);
  const [position, setPosition] = useState<LatLon | null>(null);
  const [etaMin, setEtaMin] = useState<number>(draft?.route.minutes ?? 0);
  const [viewers, setViewers] = useState(0);
  const [status, setStatus] = useState<RelayStatus | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [closures, setClosures] = useState<Hazard[]>([]);
  const [stopOpen, setStopOpen] = useState(false);
  const [pin, setPin] = useState("");
  const [pinError, setPinError] = useState(false);
  const [endedText, setEndedText] = useState(text.ended);

  const relay = useRef<RelayWalker | null>(null);
  const sim = useRef<SimGeo | null>(null);
  const watchId = useRef<number | null>(null);
  const hazardWs = useRef<WebSocket | null>(null);
  const monitor = useRef<AlertMonitor | null>(null);
  const routeRef = useRef<RouteOption | null>(draft?.route ?? null);
  const posRef = useRef<LatLon | null>(null);
  const sent = useRef(0);
  const routeDirty = useRef(true);
  const pendingAlert = useRef<AlertKind | null>(null);
  const rerouting = useRef(false);
  const startedAt = useRef(0);
  const finished = useRef(false);

  useEffect(() => {
    if (meta?.demo_mode === false && "geolocation" in navigator) setSource("gps");
  }, [meta?.demo_mode]);

  useEffect(() => () => teardown(), []);   // leaving the page ends the walk's sensors and sockets

  if (!draft || !route) {
    return (
      <div className="page">
        <NavBar />
        <div className="page-card">
          <p>{text.noRoute}</p>
          <Link className="btn-primary inline" to="/">{text.backToPlan}</Link>
        </div>
      </div>
    );
  }
  const destination = draft.destination;

  function teardown() {
    sim.current?.stop();
    if (watchId.current !== null) navigator.geolocation.clearWatch(watchId.current);
    watchId.current = null;
    hazardWs.current?.close();
    hazardWs.current = null;
  }

  async function send(u: WalkerUpdate) {
    try {
      await relay.current?.send(u);
    } catch {
      /* the relay reconnects on its own; a missed update is replaced by the next one */
    }
  }

  function update(p: GeoPoint, extra: Partial<WalkerUpdate> = {}): WalkerUpdate {
    const r = routeRef.current!;
    const withRoute = routeDirty.current || sent.current % ROUTE_RESEND_EVERY === 0;
    routeDirty.current = false;
    sent.current += 1;
    return {
      lat: p.lat, lon: p.lon, accuracy_m: p.accuracy_m, ts: p.ts,
      status: "walking",
      eta_min: remainingMetres([p.lat, p.lon], r.geometry) / paceOf(r),
      ...(withRoute ? { route: { route_id: r.route_id, label: r.label, geometry: r.geometry } } : {}),
      ...extra,
    };
  }

  function onFix(p: GeoPoint) {
    if (finished.current) return;
    posRef.current = { lat: p.lat, lon: p.lon };
    setPosition(posRef.current);
    const r = routeRef.current!;
    setEtaMin(remainingMetres([p.lat, p.lon], r.geometry) / paceOf(r));
    const fired = monitor.current!.update({ lat: p.lat, lon: p.lon, ts: p.ts });
    const alert = pendingAlert.current ?? fired[0] ?? null;
    pendingAlert.current = null;
    const u = update(p, alert
      ? { alert: { kind: alert, ts: p.ts }, status: alert === "arrived" ? "arrived" : alert === "rerouted" ? "rerouted" : "walking" }
      : {});
    if (relay.current) void send(u);
    if (alert && alert !== "arrived" && alert !== "rerouted" && share.kind !== "nobody") {
      push(text.alertSent[alert]);
      logActivity("alert", text.alertSent[alert]);
    }
    if (fired.includes("arrived")) void finish("arrived");
  }

  async function reroute() {
    const here = posRef.current;
    if (rerouting.current || !here) return;
    rerouting.current = true;
    try {
      const res = await api.reroute({ position: here, destination, mode: draft?.mode ?? "walk" });
      const best = res.routes.find((r) => r.route_id === res.decision.recommended_route_id) ?? res.routes[0];
      routeRef.current = best;
      setRoute(best);
      sim.current?.setRoute(best.geometry as [number, number][]);
      monitor.current?.setRoute(best.geometry, best.minutes, Date.now());
      routeDirty.current = true;
      pendingAlert.current = "rerouted";
      push(text.rerouted, { ring: true });
    } catch {
      push(text.rerouteFailed, { urgent: true, ring: true });
    } finally {
      rerouting.current = false;
    }
  }

  function watchHazards() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    const ws = new WebSocket(`${proto}//${location.host}/api/hazards/stream`);
    hazardWs.current = ws;
    const hits = (edgeIds: number[]) => {
      const mine = new Set(routeRef.current?.edge_ids ?? []);
      return edgeIds.some((e) => mine.has(e));
    };
    ws.onmessage = (ev) => {
      const msg = JSON.parse(ev.data as string);
      if (msg.type === "snapshot") {
        setClosures(msg.hazards);
        if (msg.hazards.some((h: Hazard) => hits(h.edge_ids))) void reroute();
      } else if (msg.type === "hazard.added") {
        setClosures((c) => [...c, msg.hazard]);
        if (hits(msg.hazard.edge_ids)) void reroute();
      } else if (msg.type === "hazard.removed") {
        setClosures((c) => c.filter((h) => h.hazard_id !== msg.hazard_id));
      }
    };
  }

  async function createJourney() {
    if (share.kind === "nobody") return null;
    if (share.kind === "family") {
      const device = await ensureDeviceKey(account!);
      const detail: FamilyDetail = await accountApi.family(share.fid);
      const { created, key, keyB64 } = await startFamilyWalk(detail, device);
      return { created, key, keyB64 };
    }
    const created = await api.createJourney();
    const key = await generateKey();
    const keyB64 = await exportKeyB64url(key);
    setLink(buildShareLink(created.journey_id, created.viewer_token, keyB64));
    return { created, key, keyB64 };
  }

  async function start() {
    setError(null);
    if (source === "gps" && !("geolocation" in navigator)) {
      setError(text.noGps);
      return;
    }
    setPhase("starting");
    try {
      const j = await createJourney();
      if (j) {
        try {
          sessionStorage.setItem(`waykin:journey:${j.created.journey_id}`, JSON.stringify({
            walker_token: j.created.walker_token, viewer_token: j.created.viewer_token, key_b64: j.keyB64 }));
        } catch {
          /* only needed to survive a reload */
        }
        const r = new RelayWalker({ journeyId: j.created.journey_id, walkerToken: j.created.walker_token,
          key: j.key, relayMode: j.created.relay_mode });
        r.onStatus(setStatus);
        r.onViewers((n, label, joined) => {
          setViewers(n);
          if (joined) push(text.viewerJoined(label ?? null));
        });
        r.connect();
        relay.current = r;
      }
    } catch (e) {
      setPhase("setup");
      setError(e instanceof Error ? e.message : String(e));
      return;
    }
    const r = routeRef.current!;
    startedAt.current = Date.now();
    monitor.current = new AlertMonitor({
      route: r.geometry, start: r.geometry[0] as [number, number],
      destination: [destination.lat, destination.lon], startTs: startedAt.current, etaMin: r.minutes,
    });
    watchHazards();
    setPhase("walking");
    if (source === "sim") {
      sim.current = new SimGeo(r.geometry as [number, number][], { speedMultiplier: 5, intervalMs: 1000, metresPerMin: paceOf(r) });
      sim.current.start(onFix);
    } else {
      watchId.current = navigator.geolocation.watchPosition(
        (p) => onFix({ lat: p.coords.latitude, lon: p.coords.longitude, accuracy_m: p.coords.accuracy, ts: p.timestamp }),
        (err) => {
          if (err.code === err.PERMISSION_DENIED) {
            void finish("stopped");
            setPhase("setup");
            setError(text.denied);
          }
        },
        { enableHighAccuracy: true, maximumAge: 2000 },
      );
    }
  }

  /** Normal and alert-PIN endings look identical on screen and to the server: one final update, then "end". */
  async function finish(reason: "arrived" | "stopped", duress = false) {
    if (finished.current) return;
    finished.current = true;
    teardown();
    const here = posRef.current;
    if (relay.current && here) {
      const last: GeoPoint = { lat: here.lat, lon: here.lon, accuracy_m: 10, ts: Date.now() };
      await send(update(last, {
        status: reason === "arrived" ? "arrived" : "walking",
        alert: duress ? { kind: "duress", ts: last.ts } : null,
      }));
    }
    relay.current?.end(reason);
    relay.current = null;
    const minutes = (Date.now() - startedAt.current) / 60_000;
    logActivity("walk", text.logWalk(draft!.originLabel ?? "start", draft!.destinationLabel ?? "destination", minutes));
    setEndedText(reason === "arrived" ? text.arrivedDone : text.ended);
    setPhase("ended");
  }

  async function confirmStop() {
    if (!hasPins()) {
      setStopOpen(false);
      await finish("stopped");
      return;
    }
    const which = await checkPin(pin);
    if (!which) {
      setPinError(true);
      return;
    }
    setStopOpen(false);
    setPin("");
    await finish("stopped", which === "alert");
  }

  async function copyLink() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard blocked: the link is selectable */
    }
  }

  const familyName = share.kind === "family" ? families.find((f) => f.family_id === share.fid)?.name ?? "" : "";
  const sharingLabel = share.kind === "family" ? text.sharingFamily : share.kind === "link" ? text.sharingLink : text.sharingNobody;

  return (
    <div className="app-shell">
      <div className="map-stage">
        {meta ? (
          <MapView bbox={meta.bbox} showBBox={false}>
            <TrackLayer route={route.geometry} position={position} closures={closures} />
          </MapView>
        ) : null}
        <BannerStack banners={banners} onDismiss={dismiss} />
      </div>
      <aside className="sheet">
        <header className="sheet-head">
          <h1>{text.title}</h1>
          <NavBar />
        </header>

        {phase === "setup" || phase === "starting" ? (
          <div className="walk-setup">
            <p className="walk-summary">
              <strong>{text.minutes(route.minutes)}</strong> · {draft.originLabel ?? ""} → {draft.destinationLabel ?? ""}
            </p>
            <fieldset className="choice">
              <legend>{text.shareWith}</legend>
              {families.map((f) => (
                <label key={f.family_id}>
                  <input type="radio" name="share" checked={share.kind === "family" && share.fid === f.family_id}
                    onChange={() => setShare({ kind: "family", fid: f.family_id })} />
                  {text.shareFamily(f.name)}
                </label>
              ))}
              <label>
                <input type="radio" name="share" checked={share.kind === "link"} onChange={() => setShare({ kind: "link" })} />
                {text.shareLink}
              </label>
              <label>
                <input type="radio" name="share" checked={share.kind === "nobody"} onChange={() => setShare({ kind: "nobody" })} />
                {text.shareNobody}
              </label>
              {!account ? <Link to="/login?next=/walk" className="hint">{text.signInForFamily}</Link> : null}
            </fieldset>
            <fieldset className="choice">
              <legend>{text.location}</legend>
              <label>
                <input type="radio" name="src" checked={source === "gps"} onChange={() => setSource("gps")} />
                {text.useGps}
              </label>
              <label>
                <input type="radio" name="src" checked={source === "sim"} onChange={() => setSource("sim")} />
                {text.simulate}
              </label>
            </fieldset>
            <section className="before" aria-label={text.beforeTitle}>
              <h2>{text.beforeTitle}</h2>
              {share.kind === "nobody" ? <p>{text.beforeNobody}</p> : (
                <>
                  <p>{share.kind === "family" ? text.beforeWho(familyName) : text.beforeLink}</p>
                  <p>{text.beforeServer}</p>
                </>
              )}
            </section>
            {error ? <p className="notice">{error}</p> : null}
            <button type="button" className="btn-primary find" disabled={phase === "starting"} onClick={() => void start()}>
              {phase === "starting" ? text.starting : text.start}
            </button>
          </div>
        ) : null}

        {phase === "walking" ? (
          <div className="walk-live">
            <div className="status-bar">
              <span>
                <strong>{sharingLabel}</strong>
                {share.kind !== "nobody" ? <> · {text.viewing(viewers)}</> : null}
                {status === "reconnecting" ? <> · {text.reconnecting}</> : null}
              </span>
              <button type="button" className="btn-quiet" onClick={() => { setPinError(false); setStopOpen(true); }}>
                {text.stop}
              </button>
            </div>
            <p className="walk-eta">{text.eta(etaMin)}</p>
            {link ? (
              <div className="share-link">
                <label htmlFor="share-link">{text.linkTitle}</label>
                <input id="share-link" readOnly value={link} onFocus={(e) => e.currentTarget.select()} />
                <div className="row">
                  <button type="button" className="btn-quiet" onClick={() => void copyLink()}>{copied ? text.copied : text.copy}</button>
                  {"share" in navigator ? (
                    <button type="button" className="btn-quiet" onClick={() => void navigator.share({ url: link }).catch(() => undefined)}>
                      {text.share}
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
            <button type="button" className="btn-primary find" onClick={() => void finish("arrived")}>{text.arrived}</button>
          </div>
        ) : null}

        {phase === "ended" ? (
          <div className="walk-ended">
            <p className="walk-done">{endedText}</p>
            <button type="button" className="btn-primary find" onClick={() => navigate("/")}>{text.newWalk}</button>
          </div>
        ) : null}
      </aside>

      {stopOpen ? (
        <div className="modal" role="dialog" aria-modal="true" aria-labelledby="stop-title">
          <div className="modal-card">
            <h2 id="stop-title">{text.stopTitle}</h2>
            {hasPins() ? (
              <>
                <label htmlFor="stop-pin">{text.pinPrompt}</label>
                <input id="stop-pin" inputMode="numeric" autoComplete="off" type="password" value={pin}
                  onChange={(e) => { setPin(e.target.value); setPinError(false); }} />
                {pinError ? <p className="notice">{text.pinWrong}</p> : null}
              </>
            ) : null}
            <div className="row">
              <button type="button" className="btn-quiet" onClick={() => setStopOpen(false)}>{text.cancel}</button>
              <button type="button" className="btn-primary inline" onClick={() => void confirmStop()}>{text.confirmStop}</button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
