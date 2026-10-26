import { FootballThief } from "./BrandMark";

const LIMB = "#F2EAD8";

/**
 * "You're getting fleeced": the football thief (same art as the logo) running off with a sack of
 * your wool. Purely decorative.
 */
export function ThiefMascot({ size = 120, className }: { size?: number; className?: string }) {
  return (
    <svg viewBox="0 0 120 100" width={size} height={(size * 100) / 120} className={className} aria-hidden>
      {/* ground shadow and speed lines */}
      <ellipse cx="68" cy="90" rx="30" ry="3" fill="#0B0E14" opacity="0.5" />
      <path d="M4 66H18M8 74H24M2 82H16" stroke="#00CEB8" strokeWidth="2.5" strokeLinecap="round" opacity="0.55" />

      {/* legs and sneakers */}
      <g fill="none" stroke={LIMB} strokeWidth="4.5" strokeLinecap="round" strokeLinejoin="round">
        <path d="M63 58Q56 70 46 74" />
        <path d="M77 57Q87 68 85 82" />
      </g>
      <ellipse cx="42" cy="74" rx="6" ry="3.6" fill="#00CEB8" transform="rotate(-25 42 74)" />
      <ellipse cx="89" cy="84" rx="6.5" ry="3.6" fill="#00CEB8" />

      {/* the sack of wool, slung over the shoulder */}
      <path
        d="M36 24C20 26 11 42 17 55C23 65 44 64 49 52C53 41 46 28 36 24Z"
        fill="#E4D9C0"
        stroke="#C9BFA6"
        strokeWidth="1.5"
      />
      <g fill="#F7F1E3">
        <circle cx="31" cy="21" r="4" />
        <circle cx="37" cy="18" r="4.5" />
        <circle cx="43" cy="21" r="4" />
      </g>
      <path d="M30 26Q37 29 43 26" stroke="#8B5A2B" strokeWidth="2.2" fill="none" strokeLinecap="round" />

      {/* arms and gloves */}
      <g fill="none" stroke={LIMB} strokeWidth="4" strokeLinecap="round">
        <path d="M56 40Q46 34 40 28" />
        <path d="M86 46Q97 49 100 58" />
      </g>
      <circle cx="39" cy="27" r="4" fill={LIMB} />
      <circle cx="100" cy="59" r="4" fill={LIMB} />

      {/* the thief */}
      <g transform="translate(38 10) scale(2)">
        <FootballThief />
      </g>
    </svg>
  );
}
