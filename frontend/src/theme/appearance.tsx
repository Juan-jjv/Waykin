import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";

export type Appearance = "light" | "dark";

const STORAGE_KEY = "waykin:appearance";

interface AppearanceContextValue {
  appearance: Appearance;
  toggle: () => void;
}

const AppearanceContext = createContext<AppearanceContextValue | null>(null);

function readAppearance(): Appearance {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

export function AppearanceProvider({ children }: { children: ReactNode }) {
  const [appearance, setAppearance] = useState<Appearance>(readAppearance);

  const toggle = useCallback(() => {
    setAppearance((current) => {
      const next: Appearance = current === "light" ? "dark" : "light";
      document.documentElement.dataset.theme = next;
      try {
        localStorage.setItem(STORAGE_KEY, next);
      } catch {
        /* Storage can be blocked. The theme still applies for this visit. */
      }
      return next;
    });
  }, []);

  const value = useMemo(() => ({ appearance, toggle }), [appearance, toggle]);

  return <AppearanceContext.Provider value={value}>{children}</AppearanceContext.Provider>;
}

export function useAppearance(): AppearanceContextValue {
  const value = useContext(AppearanceContext);
  if (!value) {
    throw new Error("useAppearance must be used within AppearanceProvider");
  }
  return value;
}
