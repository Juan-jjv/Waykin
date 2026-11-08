// Share-link viewer: /f/:id#t=<viewer token>&k=<walk key>. The token and key stay in the fragment, which the
// browser never sends to the server; it is removed from the address bar as soon as it is read.
import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { useMeta } from "../api/hooks";
import { FollowView } from "../components/FollowView";
import { NavBar } from "../components/NavBar";
import { followText } from "../copy/familyStrings";
import { importKeyB64url } from "../lib/crypto";

const NAME_KEY = "waykin:viewer-name";

function readFragment(id: string | undefined): { token: string; k: string | null } | null {
  const store = `waykin:link:${id}`;
  const p = new URLSearchParams(location.hash.replace(/^#/, ""));
  const token = p.get("t");
  if (token) {
    try {
      sessionStorage.setItem(store, JSON.stringify({ token, k: p.get("k") }));
    } catch {
      /* fine: just won't survive a reload */
    }
    history.replaceState(null, "", location.pathname);
    return { token, k: p.get("k") };
  }
  try {
    const raw = sessionStorage.getItem(store);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function FamilyPage() {
  const { id } = useParams();
  const meta = useMeta().data;
  const frag = useMemo(() => readFragment(id), [id]);
  const [name, setName] = useState(() => {
    try {
      return localStorage.getItem(NAME_KEY) ?? "";
    } catch {
      return "";
    }
  });
  const [started, setStarted] = useState(false);
  const [key, setKey] = useState<CryptoKey | undefined>(undefined);
  const [bad, setBad] = useState(false);

  useEffect(() => {
    if (!frag?.k) return;
    importKeyB64url(frag.k, "decrypt").then(setKey).catch(() => setBad(true));
  }, [frag?.k]);

  if (!id || !frag || bad || (meta?.relay_mode === "e2ee" && !frag.k)) {
    return (
      <div className="page">
        <NavBar />
        <div className="page-card"><p>{followText.badLink}</p></div>
      </div>
    );
  }

  if (!started || !meta || (meta.relay_mode === "e2ee" && !key)) {
    return (
      <div className="page">
        <NavBar />
        <div className="page-card">
          <label htmlFor="viewer-name">{followText.yourName}</label>
          <input id="viewer-name" maxLength={40} value={name} onChange={(e) => setName(e.target.value)} />
          <button type="button" className="btn-primary find" disabled={!meta} onClick={() => {
            try {
              localStorage.setItem(NAME_KEY, name.trim());
            } catch {
              /* optional */
            }
            setStarted(true);
          }}>
            {followText.follow}
          </button>
        </div>
      </div>
    );
  }

  return (
    <FollowView journeyId={id} viewerToken={frag.token} walkKey={key} relayMode={meta.relay_mode}
      label={name.trim() || undefined} walkerName={followText.someone} />
  );
}
