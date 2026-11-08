import type { AbstainReason } from "../api/types";
import { abstainBody, abstainCopy, strings } from "../copy/strings";

export function AbstainCard({ reason, maxExtra }: { reason: AbstainReason; maxExtra: number }) {
  const copy = abstainCopy[reason];

  return (
    <article className="abstain-card">
      <p className="kicker">{strings.noRecommendation}</p>
      <h3>{copy.headline}</h3>
      <p>{abstainBody(reason, maxExtra)}</p>
      <details>
        <summary>{strings.whyAbstain}</summary>
        <p>{strings.abstainDisclosure(maxExtra)}</p>
      </details>
    </article>
  );
}
