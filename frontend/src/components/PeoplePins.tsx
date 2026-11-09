import { useEffect, useRef } from "react";
import { Marker, Popup, type PositionAnchor } from "maplibre-gl";
import type { DemoPerson, LatLon } from "../api/types";
import { strings } from "../copy/strings";
import { avatarFor } from "../family/avatars";
import { useWaykinMap } from "../map/context";

// The pin is a 44px photo on a tail whose tip is the person's position (52px tall in all). MapLibre puts the card on
// whichever side has room, so each side clears the photo by the same 8px instead of one distance from the tip.
const PIN_POPUP_OFFSET: Record<PositionAnchor, [number, number]> = {
  center: [0, -26],
  top: [0, 8],
  bottom: [0, -60],
  left: [30, -30],
  right: [-30, -30],
  "top-left": [16, 0],
  "top-right": [-16, 0],
  "bottom-left": [16, -56],
  "bottom-right": [-16, -56],
};

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
    const popup = new Popup({ closeButton: false, closeOnClick: true, className: "wk-popup", offset: PIN_POPUP_OFFSET });
    const markers = people.map((person) => {
      const marker = new Marker({ element: personElement(person.display_name), anchor: "bottom" })
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
  const photo = avatarFor(name);
  if (photo) {
    avatar.classList.add("has-photo");
    avatar.style.backgroundImage = `url("${photo.src}")`;
    avatar.style.backgroundSize = photo.size;
    avatar.style.backgroundPosition = photo.position;
  } else {
    avatar.textContent = name.slice(0, 1).toUpperCase();
  }
  wrap.append(avatar);
  return wrap;
}
