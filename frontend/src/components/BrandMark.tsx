import { useId } from "react";

/**
 * "The Fleecer": a masked robber with a wool collar, the app's logo.
 * Same artwork as public/favicon.svg (keep the two in sync).
 */
export function BrandMark({ size = 24 }: { size?: number }) {
  const clip = useId(); // unique per instance, so two marks on a page don't share a clip path
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} aria-hidden>
      <defs>
        <clipPath id={clip}>
          <circle cx="16" cy="16.5" r="11" />
        </clipPath>
      </defs>
      <rect width="32" height="32" rx="7" fill="#151B28" />
      <circle cx="16" cy="16.5" r="11" fill="#0B0E14" />
      <g clipPath={`url(#${clip})`}>
        <path d="M4.5 15.5Q4.5 4.5 16 4.5Q27.5 4.5 27.5 15.5Z" fill="#3A4357" />
        <path d="M10.5 7V13.5M16 5.2V13.5M21.5 7V13.5" stroke="#252C3D" strokeWidth="1.3" />
        <rect x="4.5" y="13.2" width="23" height="3.4" fill="#55607A" />
        <g fill="#F2EAD8">
          <circle cx="9.5" cy="25.5" r="3.2" />
          <circle cx="13.5" cy="26.8" r="3.3" />
          <circle cx="18.5" cy="26.8" r="3.3" />
          <circle cx="22.5" cy="25.5" r="3.2" />
        </g>
      </g>
      <path d="M8.2 19.6Q10.8 17.2 13.9 19.1Q11.2 21 8.2 19.6Z" fill="#F2EAD8" />
      <path d="M23.8 19.6Q21.2 17.2 18.1 19.1Q20.8 21 23.8 19.6Z" fill="#F2EAD8" />
      <circle cx="11.6" cy="19.3" r="0.9" fill="#0B0E14" />
      <circle cx="20.4" cy="19.3" r="0.9" fill="#0B0E14" />
      <circle cx="16" cy="16.5" r="11" fill="none" stroke="#00CEB8" strokeWidth="1.8" />
    </svg>
  );
}
