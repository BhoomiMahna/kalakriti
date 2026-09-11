// Minimal line icons (currentColor, 24x24). No emoji anywhere in the UI.
const S = ({ children, size = 24, className = "", stroke = 2 }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={stroke}
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
  >
    {children}
  </svg>
);

export const IconCamera = (p) => (
  <S {...p}>
    <path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" />
    <circle cx="12" cy="13" r="4" />
  </S>
);
export const IconMic = (p) => (
  <S {...p}>
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </S>
);
export const IconStop = (p) => (
  <S {...p}>
    <rect x="6" y="6" width="12" height="12" rx="2" />
  </S>
);
export const IconHome = (p) => (
  <S {...p}>
    <path d="M3 9.5 12 3l9 6.5" />
    <path d="M5 10v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V10" />
  </S>
);
export const IconPlus = (p) => (
  <S {...p}>
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </S>
);
export const IconUser = (p) => (
  <S {...p}>
    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
    <circle cx="12" cy="7" r="4" />
  </S>
);
export const IconCheck = (p) => (
  <S {...p}>
    <polyline points="20 6 9 17 4 12" />
  </S>
);
export const IconChevronLeft = (p) => (
  <S {...p}>
    <polyline points="15 18 9 12 15 6" />
  </S>
);
export const IconX = (p) => (
  <S {...p}>
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </S>
);
export const IconAlert = (p) => (
  <S {...p}>
    <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
    <line x1="12" y1="9" x2="12" y2="13" />
    <line x1="12" y1="17" x2="12.01" y2="17" />
  </S>
);
export const IconBox = (p) => (
  <S {...p}>
    <path d="M21 8V21H3V8" />
    <rect x="1" y="3" width="22" height="5" rx="1" />
    <line x1="10" y1="12" x2="14" y2="12" />
  </S>
);
export const IconStore = (p) => (
  <S {...p}>
    <path d="M3 9 4 4h16l1 5" />
    <path d="M4 9v11a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1V9" />
    <path d="M3 9a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0" />
  </S>
);
export const IconReceipt = (p) => (
  <S {...p}>
    <path d="M5 3h14v18l-3-2-2 2-2-2-2 2-2-2-1 2z" />
    <line x1="9" y1="8" x2="15" y2="8" />
    <line x1="9" y1="12" x2="15" y2="12" />
  </S>
);
export const IconSend = (p) => (
  <S {...p}>
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </S>
);

// Brand mark — a small loom/weave glyph.
export const Logo = ({ size = 56 }) => (
  <svg width={size} height={size} viewBox="0 0 48 48" fill="none">
    <rect x="4" y="4" width="40" height="40" rx="12" fill="#647F45" />
    <path
      d="M14 16h20M14 24h20M14 32h20"
      stroke="#F4F6EF"
      strokeWidth="2.5"
      strokeLinecap="round"
    />
    <path
      d="M18 12v24M30 12v24"
      stroke="#CCD9B9"
      strokeWidth="2.5"
      strokeLinecap="round"
    />
  </svg>
);
