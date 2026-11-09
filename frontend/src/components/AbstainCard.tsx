import type { AbstainReason } from "../api/types";
import { abstainBody, abstainCopy, strings } from "../copy/strings";
import { ChevronIcon, InfoIcon } from "./icons";

export function AbstainCard({ reason, maxExtra }: { reason: AbstainReason; maxExtra: number }) {
  const copy = abstainCopy[reason];

  return (
    <article className="abstain-card">
      <div className="abstain-head">
        <span className="abstain-icon" aria-hidden="true">
          <InfoIcon />
        </span>
        <div>
          <p className="kicker">{strings.noRecommendation}</p>
          <h3>{copy.headline}</h3>
        </div>
      </div>
      <p>{abstainBody(reason, maxExtra)}</p>
      <details>
        <summary>
          {strings.whyAbstain}
          <ChevronIcon />
        </summary>
        <p>{strings.abstainDisclosure(maxExtra)}</p>
      </details>
    </article>
  );
}
