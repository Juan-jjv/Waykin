import { useState } from "react";
import type { Provenance } from "../api/tmp-types";
import { formatAsOf } from "../copy/format";
import { strings } from "../copy/strings";

export function ProvenanceBanner({ provenance }: { provenance: Provenance }) {
  const [open, setOpen] = useState(false);

  return (
    <div className="provenance">
      <p className="prov-source">
        {provenance.source_label} · {strings.asOf(formatAsOf(provenance.as_of))}
      </p>
      <p className="prov-units">{provenance.units}</p>
      <button
        type="button"
        className="prov-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        {open ? strings.hideDetails : strings.showDetails}
      </button>
      {open ? <p className="prov-disclaimer">{provenance.disclaimer}</p> : null}
      <p className="prov-credit">{strings.mapCredit}</p>
    </div>
  );
}
