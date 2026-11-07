import { Link, useParams } from "react-router-dom";
import { strings } from "../copy/strings";

/** Phase 3 (H22–H29): relay walker, SimGeo, hazard stream and reroute. */
export function WalkPage() {
  const { id } = useParams();
  return (
    <div className="fatal">
      <div className="fatal-card">
        <p>{strings.walkPlaceholder}</p>
        <p className="hint">{strings.journey(id)}</p>
        <Link to="/">{strings.backToPlan}</Link>
      </div>
    </div>
  );
}
