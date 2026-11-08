import { useEffect, useId, useRef, useState, type KeyboardEvent } from "react";
import { searchPlaces, type Place } from "../api/geocode";
import { strings } from "../copy/strings";

const MIN_CHARS = 3;
const DEBOUNCE_MS = 300;

type Status = "idle" | "loading" | "done" | "error";

/** A ready-made choice shown before the person types, such as "Your location" or a family member. */
export interface QuickPlace {
  key: string;
  label: string;
  hint?: string;
  /** Resolve to a place; may ask the browser for the position. Reject with a message to show. */
  pick: () => Place | Promise<Place>;
}

export function PlaceSearch({
  label,
  placeholder,
  value,
  bbox,
  onSelect,
  quick = [],
}: {
  label: string;
  placeholder: string;
  value: string | null;
  bbox: number[];
  onSelect: (place: Place) => void;
  quick?: QuickPlace[];
}) {
  const listId = useId();
  const [text, setText] = useState(value ?? "");
  const [results, setResults] = useState<Place[]>([]);
  const [status, setStatus] = useState<Status>("idle");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [quickNote, setQuickNote] = useState<string | null>(null);
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

  async function chooseQuick(option: QuickPlace) {
    setQuickNote(strings.locating);
    try {
      const place = await option.pick();
      setQuickNote(null);
      choose(place);
    } catch (error) {
      setQuickNote(error instanceof Error ? error.message : strings.locationUnavailable);
      setOpen(true);
    }
  }

  // Before the person types a search, the list offers the quick choices instead of search results.
  const showingQuick = quick.length > 0 && (!editing.current || text.trim().length < MIN_CHARS);
  const count = showingQuick ? quick.length : results.length;

  function pick(index: number) {
    if (showingQuick) void chooseQuick(quick[index]);
    else choose(results[index]);
  }

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown" && count > 0) {
      event.preventDefault();
      setOpen(true);
      setActive((i) => (i + 1) % count);
    } else if (event.key === "ArrowUp" && count > 0) {
      event.preventDefault();
      setActive((i) => (i <= 0 ? count - 1 : i - 1));
    } else if (event.key === "Enter" && open && active >= 0 && active < count) {
      event.preventDefault();
      pick(active);
    } else if (event.key === "Escape") {
      setOpen(false);
    }
  }

  const showList = open && (showingQuick || status !== "idle");

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
            setQuickNote(null);
            if (quick.length > 0) setActive(-1);
            if (quick.length > 0 || results.length > 0) setOpen(true);
          }}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
          onKeyDown={onKeyDown}
        />
      </label>
      {showList ? (
        <ul className="place-results" id={listId} role="listbox" aria-label={label}>
          {showingQuick
            ? quick.map((option, index) => (
                <li
                  key={option.key}
                  id={`${listId}-${index}`}
                  role="option"
                  aria-selected={index === active}
                  className={index === active ? "place-option quick active" : "place-option quick"}
                  onMouseDown={(event) => {
                    event.preventDefault();
                    void chooseQuick(option);
                  }}
                  onMouseEnter={() => setActive(index)}
                >
                  <span className="quick-label">{option.label}</span>
                  {option.hint ? <span className="quick-hint">{option.hint}</span> : null}
                </li>
              ))
            : null}
          {showingQuick && quickNote ? <li className="place-status" role="status">{quickNote}</li> : null}
          {!showingQuick && status === "loading" ? <li className="place-status">{strings.searching}</li> : null}
          {!showingQuick && status === "error" ? <li className="place-status">{strings.searchFailed}</li> : null}
          {!showingQuick && status === "done" && results.length === 0 ? (
            <li className="place-status">{strings.noMatches}</li>
          ) : null}
          {!showingQuick && status === "done"
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
