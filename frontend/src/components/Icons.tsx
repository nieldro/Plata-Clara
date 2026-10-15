const base = {
  width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor",
  strokeWidth: 1.5, strokeLinecap: "round" as const, strokeLinejoin: "round" as const,
};

export const Icons = {
  home: (
    <svg {...base}><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></svg>
  ),
  swap: (
    <svg {...base}><path d="M7 7h13M16 3l4 4-4 4M17 17H4M8 13l-4 4 4 4" /></svg>
  ),
  card: (
    <svg {...base}><rect x="2" y="5" width="20" height="14" rx="2.5" /><path d="M2 10h20M6 15h4" /></svg>
  ),
  target: (
    <svg {...base}><circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="5" /><circle cx="12" cy="12" r="1" /></svg>
  ),
  calc: (
    <svg {...base}><rect x="4" y="2" width="16" height="20" rx="2.5" /><path d="M8 6h8M8 11h2M14 11h2M8 15h2M14 15h2M8 19h2M14 19h2" /></svg>
  ),
  upload: (
    <svg {...base}><path d="M12 16V4M7 9l5-5 5 5M4 20h16" /></svg>
  ),
  users: (
    <svg {...base}><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c0-3.6 2.9-6 6.5-6s6.5 2.4 6.5 6M16 4.5a3.5 3.5 0 0 1 0 7M18 14.5c2 .6 3.5 2.5 3.5 5.5" /></svg>
  ),
  pie: (
    <svg {...base}><circle cx="12" cy="12" r="9" /><path d="M12 3v9h9" /></svg>
  ),
  bell: (
    <svg {...base}><path d="M6 8a6 6 0 1 1 12 0c0 7 3 9 3 9H3s3-2 3-9M10.3 21a1.94 1.94 0 0 0 3.4 0" /></svg>
  ),
  spark: (
    <svg {...base}><path d="M12 3l1.9 5.6L19.5 10l-5.6 1.9L12 17.5l-1.9-5.6L4.5 10l5.6-1.4z" /><path d="M19 17l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" /></svg>
  ),
  logout: (
    <svg {...base}><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" /></svg>
  ),
};

/** Monograma «PC» de Plata Clara. */
export const Logo = ({ size = 28 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden>
    <rect width="64" height="64" rx="14" fill="#14141a" stroke="rgba(201,169,106,.4)" />
    <text x="32" y="43" textAnchor="middle" fontFamily="Cormorant Garamond, Georgia, serif" fontSize="30" fontWeight="600" fill="#c9a96a">PC</text>
  </svg>
);
