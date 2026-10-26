import { useId } from "react";

// A football lying on its long axis, tilted so it runs from lower left to upper right.
const BALL = "M2 18C5 7.5 27 7.5 30 18C27 28.5 5 28.5 2 18Z";
const BALL_TILT = "rotate(-35 16 18)";
// The beanie and the face sit almost upright on top of the ball.
const BEANIE = "M5.5 15.5C5.5 1.5 28.5 1.5 28.5 15.5Z";
const FACE_TILT = "rotate(-10 17 15)";
const TEAL = "#00CEB8";

/**
 * The football thief: a football pulled into a black knit beanie and a robber's mask. Drawn in a
 * 32x32 coordinate box so the logo and the mascot share the exact same art.
 * Same artwork as public/favicon.svg (keep the two in sync).
 */
export function FootballThief() {
  const id = useId(); // unique per instance, so several on a page don't share clip paths
  const clip = `${id}ball`;
  const hatClip = `${id}hat`;
  return (
    <g transform="translate(2.1 2.3) scale(0.87)">
      <defs>
        <clipPath id={clip}>
          <path d={BALL} transform={BALL_TILT} />
        </clipPath>
        <clipPath id={hatClip}>
          <path d={BEANIE} />
        </clipPath>
      </defs>
      {/* teal outline around the whole silhouette: stroke both shapes, then fill over the inner edges */}
      <g fill={TEAL} stroke={TEAL} strokeWidth="3.2" strokeLinejoin="round">
        <path d={BALL} transform={BALL_TILT} />
        <path d={BEANIE} transform={FACE_TILT} />
      </g>
      <path d={BALL} transform={BALL_TILT} fill="#8A4A24" />
      <g clipPath={`url(#${clip})`}>
        {/* white stripe near the tip */}
        <path d="M7 9.5Q5.4 18 7 26.5" transform={BALL_TILT} stroke="#F2EAD8" strokeWidth="1.8" fill="none" />
        <g transform={FACE_TILT}>
          {/* robber's mask */}
          <rect x="0" y="15" width="34" height="6" fill="#0B0D12" />
          {/* laces */}
          <path d="M11 24.5H18" stroke="#F2EAD8" strokeWidth="1.3" strokeLinecap="round" />
          <path d="M12.6 23.1V25.9M14.5 23.1V25.9M16.4 23.1V25.9" stroke="#F2EAD8" strokeWidth="1" strokeLinecap="round" />
        </g>
      </g>
      <g transform={FACE_TILT}>
        {/* angry eyes */}
        <path d="M8.2 17.2L14.6 18.4Q13.9 20.6 11.3 20.5Q8.6 20.3 8.2 17.2Z" fill="#FFFFFF" />
        <path d="M26.2 17.2L19.8 18.4Q20.5 20.6 23.1 20.5Q25.8 20.3 26.2 17.2Z" fill="#FFFFFF" />
        <circle cx="12" cy="19.2" r="1" fill="#0B0D12" />
        <circle cx="22.4" cy="19.2" r="1" fill="#0B0D12" />
        {/* black knit beanie with ribs and a folded cuff */}
        <path d={BEANIE} fill="#121419" />
        <path d="M9 2V12M13 2V12M17 2V12M21 2V12M25 2V12" stroke="#23262E" strokeWidth="1.1" clipPath={`url(#${hatClip})`} />
        <rect x="5" y="11.6" width="24" height="3.9" rx="1.6" fill="#1C1F26" />
        <path d="M8 12.2V14.9M11 12.2V14.9M14 12.2V14.9M17 12.2V14.9M20 12.2V14.9M23 12.2V14.9M26 12.2V14.9" stroke="#30343F" strokeWidth="0.9" />
      </g>
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
