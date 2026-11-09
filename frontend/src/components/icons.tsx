// Small line icons for the side panel. Decorative: the text next to each one carries the meaning.
import type { ReactNode } from "react";

function Icon({ children, size = 18 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      className="icon"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      {children}
    </svg>
  );
}

export const WalkIcon = () => (
  <Icon>
    <circle cx="13" cy="4.5" r="1.8" />
    <path d="M10.5 21l2-6.5 2.5 2.5V21M9 11.5l1.8-3.6c.4-.8 1.4-1.1 2.2-.7l2.5 1.3 1.5 3M12.5 14.5l-1-4.5M8 21l2.5-6.5" />
  </Icon>
);

export const CarIcon = () => (
  <Icon>
    <path d="M5 16.5V12l1.8-4.6A2 2 0 0 1 8.7 6h6.6a2 2 0 0 1 1.9 1.4L19 12v4.5" />
    <path d="M3.5 16.5h17M5 12h14" />
    <path d="M6.5 16.5V19M17.5 16.5V19" />
    <circle cx="8" cy="14.2" r=".6" fill="currentColor" />
    <circle cx="16" cy="14.2" r=".6" fill="currentColor" />
  </Icon>
);

export const SwapIcon = () => (
  <Icon>
    <path d="M8 4v15M4.5 7.5L8 4l3.5 3.5M16 20V5M12.5 16.5L16 20l3.5-3.5" />
  </Icon>
);

export const CheckIcon = ({ size }: { size?: number }) => (
  <Icon size={size}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Icon>
);

export const ChevronIcon = () => (
  <Icon size={14}>
    <path d="M9 6l6 6-6 6" />
  </Icon>
);

export const SegmentsIcon = () => (
  <Icon size={16}>
    <path d="M4 18c3-1 4-5 7-6s5 1 9-6" />
    <circle cx="11" cy="12" r="2.2" />
  </Icon>
);

export const ArrowDownIcon = () => (
  <Icon size={14}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </Icon>
);

export const EqualIcon = () => (
  <Icon size={14}>
    <path d="M6 9.5h12M6 14.5h12" />
  </Icon>
);

export const InfoIcon = () => (
  <Icon size={20}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 11v5.5M12 7.6v.2" />
  </Icon>
);

export const SparkIcon = () => (
  <Icon size={20}>
    <path d="M12 3.5l2.2 5.3 5.3 2.2-5.3 2.2L12 18.5l-2.2-5.3L4.5 11l5.3-2.2z" />
  </Icon>
);

export const ShieldIcon = ({ size = 18 }: { size?: number }) => (
  <Icon size={size}>
    <path d="M12 3l7 2.8v5.4c0 4.4-3 8.1-7 9.8-4-1.7-7-5.4-7-9.8V5.8z" />
    <path d="M12 8.2l1.1 2.3 2.5.3-1.8 1.7.5 2.5-2.3-1.2-2.3 1.2.5-2.5-1.8-1.7 2.5-.3z" fill="currentColor" stroke="none" />
  </Icon>
);

export const PlayIcon = () => (
  <Icon size={16}>
    <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
  </Icon>
);