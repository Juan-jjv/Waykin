import { useEffect, useRef, useState } from "react";
import { formatAsOf } from "../copy/format";
import { strings } from "../copy/strings";
import { CategoryFilter } from "./CategoryFilter";
import { IncidentToggle } from "./IncidentLayer";

interface MapFiltersProps {
  incidentsOn: boolean;
  onIncidents: (next: boolean) => void;
  days: number;
  onDays: (days: number) => void;
  categories: string[];
  selected: string[];
  onCategories: (next: string[]) => void;
  asOf: string;
}

export function MapFilters({
  incidentsOn,
  onIncidents,
  days,
  onDays,
  categories,
  selected,
  onCategories,
  asOf,
}: MapFiltersProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="map-filters" ref={rootRef}>
      <button
        type="button"
        className={incidentsOn ? "map-btn filter-btn" : "map-btn filter-btn off"}
        aria-label={strings.filters}
        aria-expanded={open}
        title={strings.filters}
        onClick={() => setOpen((value) => !value)}
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path
            d="M4 7h9M17 7h3M4 17h3M11 17h9"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
          <circle cx="15" cy="7" r="2" fill="none" stroke="currentColor" strokeWidth="1.75" />
          <circle cx="9" cy="17" r="2" fill="none" stroke="currentColor" strokeWidth="1.75" />
        </svg>
      </button>
      {open ? (
        <div className="filter-panel" role="dialog" aria-label={strings.filters}>
          <IncidentToggle on={incidentsOn} onChange={onIncidents} />
          <label className="filter-field">
            <span>{strings.reportedIn}</span>
            <span className="select-wrap">
              <select value={days} onChange={(event) => onDays(Number(event.target.value))}>
                {strings.dateWindows.map((window) => (
                  <option key={window.days} value={window.days}>
                    {window.label}
                  </option>
                ))}
              </select>
            </span>
          </label>
          <CategoryFilter categories={categories} selected={selected} onChange={onCategories} />
          <p className="filter-note">{strings.dateNote(formatAsOf(asOf))}</p>
        </div>
      ) : null}
    </div>
  );
}
