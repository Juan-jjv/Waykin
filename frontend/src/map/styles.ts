// A4's CSP (backend/waykin/main.py) must allow this host.
export const MAP_STYLES = {
  light: "https://tiles.openfreemap.org/styles/liberty",
  dark: "https://tiles.openfreemap.org/styles/dark",
} as const;

export type MapAppearance = keyof typeof MAP_STYLES;
