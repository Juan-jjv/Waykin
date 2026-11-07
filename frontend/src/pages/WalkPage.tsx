import { Link, useParams } from "react-router-dom";
import { STR } from "../copy/strings";

/** Phase 3 (H22–H29): relay walker, SimGeo, hazard stream and reroute. */
export function WalkPage() {
  const { id } = useParams();
  return (
    <div className="center">
      <p>{STR.walkPlaceholder}</p>
      <p className="muted small">Journey {id}</p>
      <Link to="/">Back to plan</Link>
    </div>
  );
}
