import { useEffect, useState } from "react";
import { NavBar } from "../components/NavBar";
import { accountText } from "../copy/familyStrings";
import { deviceHistory, readHistory, type HistoryEntry } from "../family/history";

export function HistoryPage() {
  const [rows, setRows] = useState<HistoryEntry[] | null>(null);

  useEffect(() => {
    readHistory().then(setRows).catch(() => setRows([]));
  }, []);

  return (
    <div className="page">
      <NavBar />
      <section className="page-card">
        <h1>{accountText.historyTitle}</h1>
        <p className="hint">{accountText.historyNote}</p>
        {rows && rows.length === 0 ? <p>{accountText.historyEmpty}</p> : null}
        <ul className="list">
          {(rows ?? []).map((r) => (
            <li key={r.id ?? r.ts} className="list-row">
              <span>{r.text}</span>
              <time className="hint" dateTime={new Date(r.ts).toISOString()}>{new Date(r.ts).toLocaleString()}</time>
            </li>
          ))}
        </ul>
        {rows && rows.length > 0 ? (
          <button type="button" className="btn-quiet" onClick={() => {
            deviceHistory.clear().then(() => setRows([])).catch(() => undefined);
          }}>{accountText.clearHistory}</button>
        ) : null}
      </section>
    </div>
  );
}
