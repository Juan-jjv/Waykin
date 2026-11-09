import { useEffect, useState } from "react";
import { accountText } from "../copy/familyStrings";
import { deviceHistory, readHistory, type HistoryEntry } from "../family/history";

/** The History pane of the main panel: activity kept on this device. */
export function HistoryPanel() {
  const [rows, setRows] = useState<HistoryEntry[] | null>(null);

  useEffect(() => {
    readHistory().then(setRows).catch(() => setRows([]));
  }, []);

  return (
    <div className="pane-stack">
      <section className="page-card">
        <h2 className="section-title">{accountText.historyTitle}</h2>
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
