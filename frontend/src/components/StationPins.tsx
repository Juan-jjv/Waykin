import { useEffect, useRef } from "react";
import { Marker, Popup } from "maplibre-gl";
import { strings } from "../copy/strings";
import { useWaykinMap } from "../map/context";
import { STATIONS, type Station } from "../map/stations";

const SHIELD_SVG =
  '<svg viewBox="0 0 24 24" width="12" height="12" aria-hidden="true" focusable="false">' +
  '<path d="M12 3l7 2.8v5.4c0 4.4-3 8.1-7 9.8-4-1.7-7-5.4-7-9.8V5.8z" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/>' +
  '<path d="M12 8.2l1.1 2.3 2.5.3-1.8 1.7.5 2.5-2.3-1.2-2.3 1.2.5-2.5-1.8-1.7 2.5-.3z" fill="currentColor"/></svg>';

/** Police stations as dark blue badges. Tapping one offers a route there. */
export function StationPins({ onRoute }: { onRoute: (station: Station) => void }) {
  const map = useWaykinMap();
  const handler = useRef(onRoute);
  handler.current = onRoute;

  useEffect(() => {
    const popup = new Popup({ closeButton: false, closeOnClick: true, className: "wk-popup", offset: 18 });
    const markers = STATIONS.map((station) => {
      const marker = new Marker({ element: stationElement(station), anchor: "center" })
        .setLngLat([station.point.lon, station.point.lat])
        .addTo(map);
      marker.getElement().addEventListener("click", (event) => {
        event.stopPropagation();
        popup.setLngLat([station.point.lon, station.point.lat])
          .setDOMContent(stationCard(station, () => popup.remove()))
          .addTo(map);
      });
      return marker;
    });

    function stationCard(station: Station, close: () => void): HTMLElement {
      const card = document.createElement("div");
      card.className = "person-card";
      const name = document.createElement("strong");
      name.textContent = station.name;
      const address = document.createElement("span");
      address.className = "person-near";
      address.textContent = `${station.agency} · ${station.address}`;
      const actions = document.createElement("div");
      actions.className = "person-actions";
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn-quiet";
      button.textContent = strings.stationRoute;
      button.addEventListener("click", () => {
        handler.current(station);
        close();
      });
      actions.append(button);
      card.append(name, address, actions);
      return card;
    }

    return () => {
      popup.remove();
      markers.forEach((marker) => marker.remove());
    };
  }, [map]);

  return null;
}

function stationElement(station: Station): HTMLElement {
  const badge = document.createElement("button");
  badge.type = "button";
  badge.className = "wk-station";
  badge.setAttribute("aria-label", station.name);
  badge.innerHTML = SHIELD_SVG;
  return badge;
}
