import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { NavBar } from "../components/NavBar";
import { accountText } from "../copy/familyStrings";
import { accountApi, useAccount } from "../family/api";
import { idb, KEYS } from "../family/idb";
import { clearPins, hasPins, savePins } from "../walk/pins";

export function AccountPage() {
  const account = useAccount();
  const me = account.data ?? null;
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [normal, setNormal] = useState("");
  const [alertPin, setAlertPin] = useState("");
  const [pinNote, setPinNote] = useState<string | null>(hasPins() ? accountText.pinsSet : null);

  if (account.isLoading) return null;
  if (!me) return <Navigate to="/login?next=/account" replace />;

  async function leave(fn: () => Promise<void>) {
    await fn();
    qc.setQueryData(["account"], null);
    qc.removeQueries({ queryKey: ["families"] });
    navigate("/");
  }

  return (
    <div className="page">
      <NavBar />
      <section className="page-card">
        <h1>{accountText.title}</h1>
        <p>{accountText.signedInAs(me.display_name, me.login)}</p>
        <div className="row">
          <button type="button" className="btn-quiet" onClick={() => void leave(accountApi.logOut)}>{accountText.logOut}</button>
          <button type="button" className="btn-quiet warn-text" onClick={() => {
            if (!confirm(accountText.confirmDelete)) return;
            void leave(async () => {
              await accountApi.deleteAccount();
              await idb.delete(KEYS, `device:${me.account_id}`).catch(() => undefined);
            });
          }}>{accountText.delete}</button>
        </div>
      </section>

      <section className="page-card form">
        <h2>{accountText.pinTitle}</h2>
        <p className="hint">{accountText.pinHelp}</p>
        <label>
          {accountText.normalPin}
          <input type="password" inputMode="numeric" autoComplete="off" value={normal} onChange={(e) => setNormal(e.target.value)} />
        </label>
        <label>
          {accountText.alertPin}
          <input type="password" inputMode="numeric" autoComplete="off" value={alertPin} onChange={(e) => setAlertPin(e.target.value)} />
        </label>
        <div className="row">
          <button type="button" className="btn-primary inline" onClick={() => {
            savePins(normal, alertPin).then((ok) => {
              setPinNote(ok ? accountText.pinsSaved : accountText.pinsInvalid);
              if (ok) {
                setNormal("");
                setAlertPin("");
              }
            });
          }}>{accountText.savePins}</button>
          {hasPins() ? (
            <button type="button" className="btn-quiet" onClick={() => {
              clearPins();
              setPinNote(null);
            }}>{accountText.clearPins}</button>
          ) : null}
        </div>
        {pinNote ? <p className="hint" role="status">{pinNote}</p> : null}
      </section>
    </div>
  );
}
