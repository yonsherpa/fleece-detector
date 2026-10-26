/**
 * The mascot: a masked thief running off with a bag of fleece (the loot). Shown at larger sizes
 * (empty states, 404, bad verdicts), where its details read. The small logo is BrandMark.
 */
export function ThiefMascot({ size = 120, className }: { size?: number; className?: string }) {
  const cream = "#F2EAD8";
  const dark = "#0B0E14";
  const mint = "#00CEB8";
  return (
    <svg viewBox="0 0 120 100" width={size} height={(size * 100) / 120} className={className} aria-hidden>
      {/* speed lines */}
      <g stroke={mint} strokeWidth="4" strokeLinecap="round" opacity="0.85">
        <path d="M4 50H20" />
        <path d="M9 61H24" />
        <path d="M3 72H17" />
      </g>
      {/* the loot: a sack of fleece with an F */}
      <path d="M27 36Q17 52 27 68Q42 80 59 69Q69 55 61 38Q54 28 42 29Q33 30 27 36Z" fill={cream} />
      <path d="M53 31Q58 26 63 28L61 34Q57 32 55 35Z" fill={cream} />
      <path d="M52 32.5Q57 35 61 33.5" fill="none" stroke={dark} strokeWidth="2" strokeLinecap="round" />
      <text
        x="43"
        y="61"
        textAnchor="middle"
        fontFamily="Inter, Arial, sans-serif"
        fontWeight="900"
        fontSize="24"
        fill={mint}
        transform="rotate(-10 43 55)"
      >
        F
      </text>
      {/* body */}
      <g stroke={cream} strokeLinecap="round" strokeLinejoin="round" fill="none">
        <path d="M80 34L71 56" strokeWidth="12" />
        <path d="M78 37L63 33" strokeWidth="6" />
        <path d="M79 40L92 46L99 40" strokeWidth="6" />
        <path d="M71 56L61 70L49 71" strokeWidth="7" />
        <path d="M71 56L84 67L91 82" strokeWidth="7" />
      </g>
      {/* head: beanie and mask */}
      <circle cx="84" cy="22" r="10" fill={cream} />
      <path d="M74 21Q74 10 84 10Q94 10 94 21Z" fill={dark} />
      <rect x="73.5" y="19" width="21" height="3.2" rx="1.6" fill="#2E3648" />
      <rect x="74" y="23.5" width="20.5" height="5" rx="2.5" fill={dark} />
      <ellipse cx="80.5" cy="26" rx="2.2" ry="1.4" fill={cream} />
      <ellipse cx="88.5" cy="26" rx="2.2" ry="1.4" fill={cream} />
      <circle cx="81.2" cy="26.1" r="0.8" fill={dark} />
      <circle cx="89.2" cy="26.1" r="0.8" fill={dark} />
    </svg>
  );
}
