import type { AbstainReason } from "../api/tmp-types";
import { abstainCopy, strings } from "../copy/strings";

export function AbstainCard({ reason }: { reason: AbstainReason }) {
  const copy = abstainCopy[reason];

  return (
    <article className="abstain-card">
      <p className="kicker">{strings.noRecommendation}</p>
      <h3>{copy.headline}</h3>
      <p>{copy.body}</p>
      <details>
        <summary>{strings.whyAbstain}</summary>
        <p>{strings.abstainDisclosure}</p>
      </details>
    </article>
  );
}
