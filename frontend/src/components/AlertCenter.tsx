import { useCallback, useState } from "react";

export type Banner = { id: number; text: string; urgent?: boolean };

/** Banners for alerts and notices, with an optional sound, vibration and system notification. */
export function useBanners() {
  const [banners, setBanners] = useState<Banner[]>([]);

  const dismiss = useCallback((id: number) => setBanners((b) => b.filter((x) => x.id !== id)), []);

  const push = useCallback((text: string, o: { urgent?: boolean; sticky?: boolean; ring?: boolean; notify?: boolean } = {}) => {
    const id = Date.now() + Math.random();
    setBanners((b) => [...b.slice(-3), { id, text, urgent: o.urgent }]);
    if (!o.sticky) setTimeout(() => dismiss(id), o.urgent ? 20_000 : 6000);
    if (o.ring) ring(o.urgent);
    if (o.notify) systemNotify(text);
  }, [dismiss]);

  return { banners, push, dismiss };
}

export function BannerStack({ banners, onDismiss }: { banners: Banner[]; onDismiss: (id: number) => void }) {
  if (banners.length === 0) return null;
  return (
    <div className="banners" role="status" aria-live="assertive">
      {banners.map((b) => (
        <button key={b.id} type="button" className={b.urgent ? "banner urgent" : "banner"} onClick={() => onDismiss(b.id)}>
          {b.text}
        </button>
      ))}
    </div>
  );
}

function ring(urgent?: boolean): void {
  try {
    navigator.vibrate?.(urgent ? [300, 120, 300, 120, 300] : [200]);
    const Ctx = window.AudioContext ?? (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!Ctx) return;
    const ctx = new Ctx();
    const beeps = urgent ? 3 : 1;
    for (let i = 0; i < beeps; i++) {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.frequency.value = urgent ? 880 : 660;
      gain.gain.value = 0.15;
      osc.connect(gain).connect(ctx.destination);
      osc.start(ctx.currentTime + i * 0.35);
      osc.stop(ctx.currentTime + i * 0.35 + 0.2);
    }
    setTimeout(() => void ctx.close(), 1500);
  } catch {
    /* sound is a nice-to-have */
  }
}

function systemNotify(text: string): void {
  try {
    if (typeof Notification !== "undefined" && Notification.permission === "granted") new Notification("WayKin", { body: text });
  } catch {
    /* some browsers only allow notifications from a service worker */
  }
}
