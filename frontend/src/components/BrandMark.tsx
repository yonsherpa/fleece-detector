import { useId } from "react";

// Football shape, drawn in a 32x32 box; the beanie sits on top of it.
const BALL = "M3 18C6 8 26 8 29 18C26 28 6 28 3 18Z";
const BEANIE = "M7.5 13C7.5 3.5 24.5 3.5 24.5 13Z";
const OUTLINE = { stroke: "#00CEB8", strokeWidth: 1.5, strokeLinejoin: "round" } as const;

/**
 * The football thief: a football wearing a knit beanie and a robber's mask. Drawn in a 32x32
 * coordinate box so the logo and the mascot share the exact same art.
 * Same artwork as public/favicon.svg (keep the two in sync).
 */
export function FootballThief() {
  const clip = useId(); // unique per instance, so several on a page don't share a clip path
  return (
    <g transform="rotate(-14 16 17)">
      <defs>
        <clipPath id={clip}>
          <path d={BALL} />
        </clipPath>
      </defs>
      <path d={BALL} fill="#8B5A2B" />
      <g clipPath={`url(#${clip})`}>
        {/* robber's mask */}
        <rect x="0" y="14" width="32" height="5.4" fill="#0B0E14" />
        {/* laces */}
        <path d="M12 23H20" stroke="#F2EAD8" strokeWidth="1.3" strokeLinecap="round" />
        <path d="M13.8 21.6V24.4M16 21.6V24.4M18.2 21.6V24.4" stroke="#F2EAD8" strokeWidth="1" strokeLinecap="round" />
      </g>
      {/* sly eyes */}
      <path d="M8.6 17Q11.4 14.9 14.3 16.4Q11.5 18.2 8.6 17Z" fill="#F2EAD8" />
      <path d="M23.4 17Q20.6 14.9 17.7 16.4Q20.5 18.2 23.4 17Z" fill="#F2EAD8" />
      <circle cx="12" cy="16.6" r="0.9" fill="#0B0E14" />
      <circle cx="20" cy="16.6" r="0.9" fill="#0B0E14" />
      <path d={BALL} fill="none" {...OUTLINE} />
      {/* knit beanie with ribs and a folded cuff */}
      <path d={BEANIE} fill="#3A4357" {...OUTLINE} />
      <path d="M12 7.6V10.6M16 6.6V10.6M20 7.6V10.6" stroke="#252C3D" strokeWidth="1.1" />
      <rect x="6.5" y="10.5" width="19" height="3.6" rx="1.6" fill="#55607A" {...OUTLINE} />
    </g>
  );
}

/** The app logo: the football thief on the navy tile (also the favicon). */
export function BrandMark({ size = 24 }: { size?: number }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden>
      <rect width="32" height="32" rx="7" fill="#151B28" />
      <FootballThief />
    </svg>
  );
}
