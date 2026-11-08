import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMeta } from "../api/hooks";
import { FollowView } from "../components/FollowView";
import { NavBar } from "../components/NavBar";
import { familyText, followText } from "../copy/familyStrings";
import { useAccount, useFamily } from "../family/api";
import { ensureDeviceKey, followKey } from "../family/session";

/** Follow a family member's walk. The walk key is opened on this device with the family key. */
export function FamilyFollowPage() {
  const { fid = "", jid = "" } = useParams();
  const me = useAccount().data ?? null;
  const meta = useMeta().data;
  const detail = useFamily(me ? fid : null).data;
  const journey = detail?.journeys.find((j) => j.journey_id === jid);
  const [key, setKey] = useState<CryptoKey | undefined>(undefined);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!me || !detail || !journey) return;
    ensureDeviceKey(me).then((device) => followKey(detail, journey, device)).then(setKey).catch(() => setFailed(true));
  }, [me, detail, journey]);

  if (failed || (detail && !journey)) {
    return (
      <div className="page">
        <NavBar />
        <div className="page-card">
          <p>{failed ? familyText.wrongDevice : followText.ended(followText.someone, "stopped")}</p>
          <Link to={`/family?f=${encodeURIComponent(fid)}`}>{familyText.title}</Link>
        </div>
      </div>
    );
  }
  if (!me || !meta || !journey || !key) {
    return <div className="fatal"><p>{followText.waiting}</p></div>;
  }
  return (
    <FollowView journeyId={jid} viewerToken={journey.viewer_token} walkKey={key} relayMode={meta.relay_mode}
      label={me.display_name} walkerName={journey.walker_display_name} />
  );
}
