import { useEffect, useRef, useState, type PointerEvent, type ReactNode } from "react";
import { strings } from "../copy/strings";

const PHONE = "(max-width: 767px)";
/** How far the handle must travel before a release counts as a swipe rather than a tap. */
const SWIPE_PX = 48;
const TAP_PX = 6;

/**
 * The main panel. On phones it is a bottom sheet that rises to fill the screen when expanded; the handle can be
 * dragged or tapped. On wider screens it is the left column and only the content changes.
 */
export function Sheet({
  expanded,
  onExpandedChange,
  header,
  paneKey,
  children,
}: {
  expanded: boolean;
  onExpandedChange: (next: boolean) => void;
  header: ReactNode;
  paneKey: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLElement>(null);
  const drag = useRef<{ startY: number; startHeight: number; dy: number } | null>(null);
  const dragged = useRef(false);
  const [dragHeight, setDragHeight] = useState<number | null>(null);

  useEffect(() => {
    ref.current?.scrollTo?.({ top: 0 });
  }, [paneKey]);

  function onPointerDown(event: PointerEvent<HTMLButtonElement>) {
    if (!ref.current || !window.matchMedia?.(PHONE).matches) return;
    drag.current = { startY: event.clientY, startHeight: ref.current.getBoundingClientRect().height, dy: 0 };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }

  function onPointerMove(event: PointerEvent<HTMLButtonElement>) {
    const current = drag.current;
    if (!current) return;
    current.dy = event.clientY - current.startY;
    if (Math.abs(current.dy) < TAP_PX) return;
    const height = Math.min(window.innerHeight, Math.max(120, current.startHeight - current.dy));
    setDragHeight(height);
  }

  function onPointerUp() {
    const current = drag.current;
    drag.current = null;
    setDragHeight(null);
    dragged.current = current != null && Math.abs(current.dy) >= TAP_PX;
    if (!current || !dragged.current) return;
    if (current.dy < -SWIPE_PX) onExpandedChange(true);
    else if (current.dy > SWIPE_PX) onExpandedChange(false);
  }

  const classes = ["sheet", expanded ? "expanded" : "", dragHeight != null ? "dragging" : ""].filter(Boolean).join(" ");

  return (
    <aside ref={ref} className={classes} style={dragHeight != null ? { height: dragHeight } : undefined}>
      <header className="sheet-head">
        <button
          type="button"
          className="sheet-grabber"
          aria-label={expanded ? strings.collapsePanel : strings.expandPanel}
          aria-expanded={expanded}
          onClick={() => {
            // A drag ends with a click too; only a plain tap or keyboard press toggles.
            if (dragged.current) {
              dragged.current = false;
              return;
            }
            onExpandedChange(!expanded);
          }}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        />
        {header}
      </header>
      <div className="sheet-pane" key={paneKey}>
        {children}
      </div>
    </aside>
  );
}
