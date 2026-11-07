import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type { FamilyDetail } from "../api/types";
import { BannerStack, useBanners } from "../components/AlertCenter";
import { NavBar } from "../components/NavBar";
import { familyText, walkText } from "../copy/familyStrings";
import { accountApi, openFamilyStream, useAccount, useFamilies, useFamily } from "../family/api";
import { logActivity } from "../family/history";
import { createFamily, ensureDeviceKey, familySecret, inviteLink, removeAndRotate, resetFamilyKey } from "../family/session";

export function FamilyHomePage() {
  const account = useAccount();
  const me = account.data ?? null;
  const families = useFamilies(Boolean(me));
  const [params, setParams] = useSearchParams();
  const selected = params.get("f") ?? families.data?.[0]?.family_id ?? null;
  const detail = useFamily(me ? selected : null);
  const qc = useQueryClient();
  const navigate = useNavigate();
  const { banners, push, dismiss } = useBanners();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [wrongDevice, setWrongDevice] = useState(false);

  useEffect(() => {
    if (me) ensureDeviceKey(me).catch(() => undefined);
  }, [me]);

  useEffect(() => {
    setLink(null);
    setWrongDevice(false);
    const d = detail.data;
    if (!me || !d) return;
    ensureDeviceKey(me).then((device) => familySecret(d, device)).catch(() => setWrongDevice(true));
  }, [me, detail.data]);

  useEffect(() => {
    if (!me) return;
    return openFamilyStream((e) => {
      const fid = typeof e.family_id === "string" ? e.family_id : null;
      if (fid) void qc.invalidateQueries({ queryKey: ["family", fid] });
      void qc.invalidateQueries({ queryKey: ["families"] });
      if (e.type === "journey.started") {
        const j = e.journey as { walker_id: string; walker_display_name: string };
        if (j.walker_id !== me.account_id) {
          push(familyText.started(j.walker_display_name), { ring: true, notify: true });
          logActivity("family", familyText.started(j.walker_display_name));
        }
      } else if (e.type === "member.joined" && e.account_id !== me.account_id) {
        push(familyText.joined(String(e.display_name)), { notify: true });
        logActivity("family", familyText.joined(String(e.display_name)));
      } else if (e.type === "member.left") {
        push(familyText.left);
      } else if (e.type === "family.key_rotated") {
        push(familyText.rotated);
      }
    });
  }, [me, qc, push]);

  async function act(fn: () => Promise<void>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  if (!me) {
    return (
      <div className="page">
        <NavBar />
        <div className="page-card">
          <h1>{familyText.title}</h1>
          <p>{familyText.signedOut}</p>
          <div className="row">
            <Link className="btn-primary inline" to="/login?next=/family">{familyText.signIn}</Link>
            <Link className="btn-quiet" to="/signup?next=/family">{familyText.signUp}</Link>
          </div>
        </div>
      </div>
    );
  }

  const d: FamilyDetail | undefined = detail.data;
  const isOwner = d?.owner_id === me.account_id;

  return (
    <div className="page">
      <NavBar />
      <BannerStack banners={banners} onDismiss={dismiss} />
      <div className="page-card">
        <h1>{familyText.title}</h1>
        {families.data && families.data.length > 1 ? (
          <div className="chips">
            {families.data.map((f) => (
              <button key={f.family_id} type="button" className={f.family_id === selected ? "chip on" : "chip"}
                onClick={() => setParams({ f: f.family_id })}>
                {f.name}
              </button>
            ))}
          </div>
        ) : null}
        {families.data?.length === 0 ? <p>{familyText.none}</p> : null}
        <form className="row" onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim()) return;
          void act(async () => {
            const created = await createFamily(name.trim(), await ensureDeviceKey(me));
            setName("");
            await qc.invalidateQueries({ queryKey: ["families"] });
            setParams({ f: created.family_id });
          });
        }}>
          <input aria-label={familyText.namePlaceholder} placeholder={familyText.namePlaceholder} maxLength={40}
            value={name} onChange={(e) => setName(e.target.value)} />
          <button type="submit" className="btn-quiet" disabled={busy || !name.trim()}>{familyText.create}</button>
        </form>
        {error ? <p className="notice">{error}</p> : null}
      </div>

      {d ? (
        <>
          {wrongDevice ? (
            <div className="notice page-note">
              <p>{isOwner ? familyText.wrongDeviceOwner : familyText.wrongDevice}</p>
              {isOwner ? (
                <button type="button" className="btn-primary inline" disabled={busy} onClick={() => void act(async () => {
                  await ensureDeviceKey(me);
                  await resetFamilyKey(d.family_id);
                  await qc.invalidateQueries({ queryKey: ["family", d.family_id] });
                })}>{familyText.resetKey}</button>
              ) : null}
            </div>
          ) : null}
          <section className="page-card">
            <h2>{familyText.live}</h2>
            {d.journeys.length === 0 ? <p className="hint">{familyText.nobodyWalking}</p> : (
              <ul className="list">
                {d.journeys.map((j) => (
                  <li key={j.journey_id} className="list-row">
                    <span>{j.walker_display_name}{j.walker_id === me.account_id ? ` (${familyText.you})` : ""}</span>
                    {j.walker_id !== me.account_id ? (
                      <button type="button" className="btn-primary inline" disabled={wrongDevice}
                        onClick={() => navigate(`/family/follow/${d.family_id}/${j.journey_id}`)}>
                        {familyText.follow}
                      </button>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="page-card">
            <h2>{d.name} · {familyText.members}</h2>
            <ul className="list">
              {d.members.map((m) => (
                <li key={m.account_id} className="list-row">
                  <span>
                    {m.display_name}
                    {m.is_owner ? <small className="pill">{familyText.owner}</small> : null}
                    {m.account_id === me.account_id ? <small className="pill">{familyText.you}</small> : null}
                  </span>
                  {isOwner && m.account_id !== me.account_id ? (
                    <button type="button" className="btn-quiet" disabled={busy} onClick={() => {
                      if (!confirm(familyText.confirmRemove(m.display_name))) return;
                      void act(async () => {
                        await removeAndRotate(d, m.account_id);
                        await qc.invalidateQueries({ queryKey: ["family", d.family_id] });
                      });
                    }}>{familyText.remove}</button>
                  ) : null}
                </li>
              ))}
            </ul>
            <div className="row">
              <button type="button" className="btn-primary inline" disabled={busy || wrongDevice} onClick={() => void act(async () => {
                setLink(await inviteLink(d, await ensureDeviceKey(me)));
              })}>{familyText.invite}</button>
              <button type="button" className="btn-quiet" disabled={busy} onClick={() => {
                if (!confirm(familyText.confirmLeave)) return;
                void act(async () => {
                  await accountApi.removeMember(d.family_id, me.account_id);
                  setParams({});
                  await qc.invalidateQueries({ queryKey: ["families"] });
                });
              }}>{familyText.leave}</button>
            </div>
            {link ? (
              <div className="share-link">
                <input readOnly aria-label={familyText.invite} value={link} onFocus={(e) => e.currentTarget.select()} />
                <p className="hint">{familyText.inviteHint}</p>
                <div className="row">
                  <button type="button" className="btn-quiet" onClick={() => {
                    navigator.clipboard.writeText(link).then(() => {
                      setCopied(true);
                      setTimeout(() => setCopied(false), 2000);
                    }).catch(() => undefined);
                  }}>{copied ? walkText.copied : walkText.copy}</button>
                  {"share" in navigator ? (
                    <button type="button" className="btn-quiet" onClick={() => void navigator.share({ url: link }).catch(() => undefined)}>
                      {walkText.share}
                    </button>
                  ) : null}
                </div>
              </div>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
