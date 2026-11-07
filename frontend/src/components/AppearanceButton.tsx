import { strings } from "../copy/strings";
import { useAppearance } from "../theme/appearance";

export function AppearanceButton() {
  const { appearance, toggle } = useAppearance();
  const label = appearance === "light" ? strings.switchToDark : strings.switchToLight;

  return (
    <button
      type="button"
      className="appearance-btn"
      onClick={toggle}
      aria-label={label}
      aria-pressed={appearance === "dark"}
      title={label}
    >
      <span className="appearance-icons" aria-hidden="true">
        <svg className="icon-sun" viewBox="0 0 24 24">
          <circle cx="12" cy="12" r="4" fill="none" stroke="currentColor" strokeWidth="1.75" />
          <path
            d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M4.8 4.8l1.6 1.6M17.6 17.6l1.6 1.6M19.2 4.8l-1.6 1.6M6.4 17.6l-1.6 1.6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
        </svg>
        <svg className="icon-moon" viewBox="0 0 24 24">
          <path
            d="M15.6 3.3a8.1 8.1 0 1 0 5.2 12.5A7 7 0 0 1 15.6 3.3z"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
        </svg>
      </span>
    </button>
  );
}
