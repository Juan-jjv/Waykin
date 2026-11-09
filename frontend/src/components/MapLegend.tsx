import { strings } from "../copy/strings";
import { SEVERITY_RAMP } from "../map/colors";
import { useAppearance } from "../theme/appearance";

/** Dot colour key: a slim vertical pill, darkest red (most serious) at the top fading to light red at the bottom. */
export function MapLegend() {
  const { appearance } = useAppearance();
  const ramp = [...SEVERITY_RAMP[appearance]].reverse().join(", ");
  return (
    <div className="map-legend" role="img" aria-label={strings.severityLegendLabel}>
      <span className="map-legend-end" aria-hidden="true">{strings.severityHigh}</span>
      <span className="map-legend-bar" style={{ background: `linear-gradient(to bottom, ${ramp})` }} />
      <span className="map-legend-end" aria-hidden="true">{strings.severityLow}</span>
    </div>
  );
}
