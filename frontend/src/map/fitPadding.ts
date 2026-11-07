export function fitPadding(): { top: number; right: number; bottom: number; left: number } {
  const wide = window.matchMedia("(min-width: 768px)").matches;
  return {
    top: wide ? 48 : 72,
    left: wide ? 48 : 28,
    right: 56,
    bottom: wide ? 48 : Math.round(window.innerHeight * 0.48),
  };
}
