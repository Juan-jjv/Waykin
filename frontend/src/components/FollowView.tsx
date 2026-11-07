import { useEffect, useRef, useState } from "react";
import { useMeta } from "../api/hooks";
import type { WalkerUpdate } from "../api/types";
import { alertText, followText } from "../copy/familyStrings";
import { logActivity } from "../family/history";
import { RelayViewer } from "../lib/relay";
import type { RelayMode, RelayStatus } from "../lib/types";
import { BannerStack, useBanners } from "./AlertCenter";
import { MapView } from "./MapView";
import { NavBar } from "./NavBar";
import { TrackLayer } from "./TrackLayer";

/** Follows one walk over the relay: live position, route, ETA, and the walker's alerts. */
export function FollowView({
  journeyId, viewerToken, walkKey, relayMode, label, walkerName,
}: {
  journeyId: string;
  viewerToken: string;
  walkKey?: CryptoKey;
  relayMode: RelayMode;
  label?: string;
  walkerName: string;
}) {
  const meta = useMeta().data;
  const { banners, push, dismiss } = useBanners();
  const [latest, setLatest] = useState<WalkerUpdate | null>(null);
  const [route, setRoute] = useState<number[][] | null>(null);
  const [ended, setEnded] = useState<string | null>(null);
  const [status, setStatus] = useState<RelayStatus>("connecting");
  const [now, setNow] = useState(Date.now());
  const [notifyOn, setNotifyOn] = useState(typeof Notification !== "undefined" && Notification.permission === "granted");
  const seen = useRef(new Set<string>());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 15_000);
    return () => clearInterval(t);
  }, []);

  useEffect(() => {
    logActivity("followed", followText.logFollow(walkerName));
    const viewer = new RelayViewer({
      journeyId, viewerToken, key: walkKey, relayMode, label,
      onStatus: setStatus,
      onUpdate: (u) => {
        setLatest(u);
        if (u.route) setRoute(u.route.geometry);
        const a = u.alert;
        const id = a ? `${a.kind}:${a.ts}` : null;
        if (a && id && !seen.current.has(id)) {
          seen.current.add(id);
          const text = alertText[a.kind](walkerName);
          const urgent = a.kind === "duress";
          push(text, { urgent, sticky: urgent, ring: true, notify: true });
          logActivity("alert", text);
        }
      },
      onSilent: (s) => push(followText.silent(walkerName, s), { ring: true, notify: true }),
      onEnded: (reason) => {
        setEnded(reason);
        push(followText.ended(walkerName, reason), { notify: true });
      },
    });
    viewer.connect();
    return () => viewer.close();
  }, [journeyId, viewerToken, walkKey, relayMode, label, walkerName, push]);

  async function enableNotifications() {
    if (typeof Notification === "undefined") return;
    setNotifyOn((await Notification.requestPermission()) === "granted");
  }

  const position = latest ? { lat: latest.lat, lon: latest.lon } : null;
  const age = latest ? (now - latest.ts) / 1000 : 0;

  return (
    <div className="app-shell">
      <div className="map-stage">
        {meta ? (
          <MapView bbox={meta.bbox} showBBox={false}>
            <TrackLayer route={route} position={position} />
          </MapView>
        ) : null}
        <BannerStack banners={banners} onDismiss={dismiss} />
      </div>
      <aside className="sheet">
        <header className="sheet-head">
          <h1>{followText.title(walkerName)}</h1>
          <NavBar />
        </header>
        {ended ? (
          <p className="walk-done">{followText.ended(walkerName, ended)}</p>
        ) : latest ? (
          <div className="walk-live">
            <p className="walk-eta">{followText.eta(latest.eta_min)}</p>
            <p className="hint">{followText.updated(Math.max(0, age))}{status === "reconnecting" ? " · reconnecting" : ""}</p>
          </div>
        ) : (
          <p className="hint">{followText.waiting}</p>
        )}
        {!ended ? (
          <div className="notify">
            <button type="button" className="btn-quiet" disabled={notifyOn} onClick={() => void enableNotifications()}>
              {notifyOn ? followText.notifyOn : followText.notify}
            </button>
            <p className="hint">{followText.notifyHint}</p>
          </div>
        ) : null}
      </aside>
    </div>
  );
}
