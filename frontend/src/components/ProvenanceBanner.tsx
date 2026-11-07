import { useState } from "react";
import type { Provenance } from "../api/types";
import { STR } from "../copy/strings";

/** Source, date, units and disclaimer. Collapsible, never removable. */
export function ProvenanceBanner({ provenance }: { provenance: Provenance }) {
  const [open, setOpen] = useState(false);
  const synthetic = provenance.source === "synthetic";
  return (
    <div className={`provenance ${synthetic ? "synthetic" : ""}`} role="note" aria-label="Data source">
      <div className="provenance-row">
        {synthetic && <strong className="badge">SYNTHETIC DATA</strong>}
        <span>{provenance.source_label}</span>
        <span className="muted"> · {STR.asOf(provenance.as_of)}</span>
        <button className="link" onClick={() => setOpen((o) => !o)}>
          {open ? STR.hideDisclaimer : STR.showDisclaimer}
        </button>
      </div>
      {open && (
        <div className="provenance-detail">
          <p>{provenance.disclaimer}</p>
          <p className="muted">Units: {provenance.units}.</p>
        </div>
      )}
    </div>
  );
}
