// /join/:fid#i=<invite token>&k=<family key>&v=<key version>. The fragment is kept in this tab only (so it
// survives signing in) and removed from the address bar at once.
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import type { InvitePreview } from "../api/types";
import { NavBar } from "../components/NavBar";
import { joinText, familyText } from "../copy/familyStrings";
import { accountApi, useAccount } from "../family/api";
import { parseInviteFragment } from "../family/keys";
import { b64urlEncode } from "../lib/crypto";
import { ensureDeviceKey, joinFamily } from "../family/session";

function readInvite(fid: string) {
  const store = `waykin:invite:${fid}`;
  if (location.hash) {
    const parsed = parseInviteFragment(location.hash);
    history.replaceState(null, "", location.pathname);
    if (parsed) {
      try {
        const frag = new URLSearchParams({ i: parsed.token, k: b64urlEncode(parsed.secret), v: String(parsed.keyVersion) });
        sessionStorage.setItem(store, `#${frag}`);
      } catch {
        /* the invite still works in this page view */
      }
      return parsed;
    }
  }
  try {
    const saved = sessionStorage.getItem(store);
    return saved ? parseInviteFragment(saved) : null;
  } catch {
    return null;
  }
}

export function JoinPage() {
  const { fid = "" } = useParams();
  const invite = useMemo(() => readInvite(fid), [fid]);
  const me = useAccount().data ?? null;
  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const qc = useQueryClient();
  const navigate = useNavigate();

  useEffect(() => {
    if (!me || !invite) return;
    accountApi.invitePreview(fid, invite.token).then(setPreview).catch(() => setError(joinText.badLink));
  }, [me, invite, fid]);

  const next = encodeURIComponent(`/join/${fid}`);
  return (
    <div className="page">
      <NavBar />
      <div className="page-card">
        <h1>{joinText.title}</h1>
        {!invite || error ? <p className="notice">{error ?? joinText.badLink}</p> : !me ? (
          <>
            <p>{joinText.signInFirst}</p>
            <div className="row">
              <Link className="btn-primary inline" to={`/login?next=${next}`}>{familyText.signIn}</Link>
              <Link className="btn-quiet" to={`/signup?next=${next}`}>{familyText.signUp}</Link>
            </div>
          </>
        ) : preview ? (
          <>
            <p>{joinText.invited(preview.invited_by, preview.family_name)}</p>
            <button type="button" className="btn-primary find" disabled={busy} onClick={() => {
              setBusy(true);
              ensureDeviceKey(me)
                .then((device) => joinFamily(fid, invite.token, invite.secret, invite.keyVersion, device))
                .then(async () => {
                  try {
                    sessionStorage.removeItem(`waykin:invite:${fid}`);
                  } catch {
                    /* nothing to clean */
                  }
                  await qc.invalidateQueries({ queryKey: ["families"] });
                  navigate(`/family?f=${encodeURIComponent(fid)}`);
                })
                .catch((e) => setError(e instanceof Error ? e.message : String(e)))
                .finally(() => setBusy(false));
            }}>
              {busy ? joinText.joining : joinText.join(preview.family_name)}
            </button>
          </>
        ) : null}
      </div>
    </div>
  );
}
