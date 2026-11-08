import { useEffect, useRef } from "react";
import { Marker, Popup } from "maplibre-gl";
import type { DemoPerson, LatLon } from "../api/types";
import { strings } from "../copy/strings";
import { useWaykinMap } from "../map/context";

interface PeoplePinsProps {
  people: DemoPerson[];
  onStart: (point: LatLon, label: string) => void;
  onEnd: (point: LatLon, label: string) => void;
}

/** Family members as named pins. Tapping one offers it as the start or end of a route. */
export function PeoplePins({ people, onStart, onEnd }: PeoplePinsProps) {
  const map = useWaykinMap();
  const handlers = useRef({ onStart, onEnd });
  handlers.current = { onStart, onEnd };

  useEffect(() => {
    const popup = new Popup({ closeButton: false, closeOnClick: true, className: "wk-popup", offset: 22 });
    const markers = people.map((person) => {
      const marker = new Marker({ element: personElement(person.display_name), anchor: "center" })
        .setLngLat([person.position.lon, person.position.lat])
        .addTo(map);
      marker.getElement().addEventListener("click", (event) => {
        event.stopPropagation();
        popup.setLngLat([person.position.lon, person.position.lat])
          .setDOMContent(personCard(person, () => popup.remove()))
          .addTo(map);
      });
      return marker;
    });

    function personCard(person: DemoPerson, close: () => void): HTMLElement {
      const card = document.createElement("div");
      card.className = "person-card";
      const name = document.createElement("strong");
      name.textContent = person.display_name;
      card.append(name);
      if (person.near) {
        const near = document.createElement("span");
        near.className = "person-near";
        near.textContent = strings.personNear(person.near);
        card.append(near);
      }
      const actions = document.createElement("div");
      actions.className = "person-actions";
      const choices: [string, "onStart" | "onEnd"][] = [[strings.startHere, "onStart"], [strings.endHere, "onEnd"]];
      for (const [label, which] of choices) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "btn-quiet";
        button.textContent = label;
        button.addEventListener("click", () => {
          handlers.current[which](person.position, person.display_name);
          close();
        });
        actions.append(button);
      }
      card.append(actions);
      return card;
    }

    return () => {
      popup.remove();
      markers.forEach((marker) => marker.remove());
    };
  }, [map, people]);

  return null;
}

function personElement(name: string): HTMLElement {
  const wrap = document.createElement("button");
  wrap.type = "button";
  wrap.className = "wk-person";
  wrap.setAttribute("aria-label", name);
  const avatar = document.createElement("span");
  avatar.className = "wk-person-avatar";
  avatar.textContent = name.slice(0, 1).toUpperCase();
  const label = document.createElement("span");
  label.className = "wk-pin-label";
  label.textContent = name;
  wrap.append(avatar, label);
  return wrap;
}
