import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { searchPlaces, type Place } from "../api/geocode";
import { strings } from "../copy/strings";

const MIN_CHARS = 3;
const DEBOUNCE_MS = 300;

type Status = "idle" | "loading" | "done" | "error";

export function PlaceSearch({
  label,
  placeholder,
  value,
  bbox,
  onSelect,
}: {
  label: string;
  placeholder: string;
  value: string | null;
  bbox: number[];
  onSelect: (place: Place) => void;
}) {
  const listId = useId();
  const [text, setText] = useState(value ?? "");
  const [results, setResults] = useState<Place[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const editing = useRef(false);

  useEffect(() => {
    editing.current = false;
    setText(value ?? "");
    setOpen(false);
  }, [value]);

  useEffect(() => {
    const query = text.trim();
    if (!editing.current || query.length < MIN_CHARS) {
      setResults([]);
      setStatus("idle");
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setStatus("loading");
      searchPlaces(query, bbox, controller.signal)
        .then((places) => {
          setResults(places);
          setActive(places.length > 0 ? 0 : -1);
          setStatus("done");
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") return;
          setResults([]);
          setStatus("error");
        });
    }, DEBOUNCE_MS);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [text, bbox]);

  function choose(place: Place) {
    editing.current = false;
    setText(place.label);
    setOpen(false);
    setResults([]);
    onSelect(place);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && results.length > 0) {
      event.preventDefault();
      setOpen(true);
      setActive((i) => (i + 1) % results.length);
    } else if (event.key === "ArrowUp" && results.length > 0) {
      event.preventDefault();
      setActive((i) => (i <= 0 ? results.length - 1 : i - 1));
    } else if (event.key === "Enter" && open && results[active]) {
      event.preventDefault();
      choose(results[active]);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const showList = open && status !== "idle";

  return (
    <div className="place-search">
      <label className="place-label">
        <span>{label}</span>
        <input
          type="search"
          role="combobox"
          aria-expanded={showList}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={showList && active >= 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          placeholder={placeholder}
          value={text}
          onChange={(event) => {
            editing.current = true;
            setText(event.target.value);
            setOpen(true);
          }}
          onFocus={(event) => {
            event.target.select();
            if (results.length > 0) setOpen(true);
          }}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKeyDown}
        />
      </label>
      {showList ? (
        <ul className="place-results" id={listId} role="listbox" aria-label={label}>
          {status === "loading" ? <li className="place-status">{strings.searching}</li> : null}
          {status === "error" ? <li className="place-status">{strings.searchFailed}</li> : null}
          {status === "done" && results.length === 0 ? <li className="place-status">{strings.noMatches}</li> : null}
          {status === "done"
            ? results.map((place, index) => (
                <li
                  key={place.label}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  className={index === active ? "place-option active" : "place-option"}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    choose(place);
                  }}
                  onMouseEnter={() => setActive(index)}
                >
                  {place.label}
                </li>
              ))
            : null}
        </ul>
      ) : null}
    </div>
  );
}
