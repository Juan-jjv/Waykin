import { useState } from "react";
import type { LatLon } from "../api/types";
import { formatDistance } from "../copy/format";
import { strings } from "../copy/strings";
import { rankStations, type Station } from "../map/stations";
import { ChevronIcon, ShieldIcon } from "./icons";

const FIRST = 3;

/** Nearby police stations as places to meet or be picked up; picking one routes there. */
export function StationList({
  from,
  note,
  onRoute,
}: {
  from: LatLon | null;
  note: string | null;
  onRoute: (station: Station) => void;
}) {
  const [all, setAll] = useState(false);
  const rows = rankStations(from);
  const shown = all ? rows : rows.slice(0, FIRST);

  return (
    <section className="stations" aria-labelledby="stations-title">
      <div className="section-head">
        <h2 id="stations-title" className="section-title">{strings.stationsTitle}</h2>
        <button type="button" className="text-btn" onClick={() => setAll((value) => !value)}>
          {all ? strings.stationsFewer : strings.stationsAll(rows.length)}
        </button>
      </div>
      <div className="group">
        {shown.map(({ station, meters }) => (
          <button key={station.id} type="button" className="preset station" onClick={() => onRoute(station)}>
            <span className="preset-tile station-tile" aria-hidden="true"><ShieldIcon size={18} /></span>
            <span className="preset-text">
              <span className="preset-name">{station.name}</span>
              <span className="preset-desc">
                {meters === null ? station.address : `${formatDistance(meters)} · ${station.address}`}
              </span>
            </span>
            <span className="preset-trail" aria-hidden="true"><ChevronIcon /></span>
          </button>
        ))}
      </div>
      {note ? <p className="notice" role="status">{note}</p> : null}
    </section>
  );
}
