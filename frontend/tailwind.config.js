/** @type {import('tailwindcss').Config} */
// "Sleeper night" theme: navy neutrals, one mint accent, Sleeper's position colors.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#10141F",
          900: "#151B28", // page
          850: "#1A2130", // raised strip / popover
          800: "#1E2535", // card
          700: "#2A3245", // border
          600: "#38415A",
          500: "#5D6679", // faint text
          400: "#8A93A6", // secondary text
          300: "#AEB5C4",
          200: "#CDD3DE",
          100: "#E9EDF5", // primary text
        },
        mint: { 300: "#7EE6DA", 400: "#33D8C6", 500: "#00CEB8", 600: "#00A896", 700: "#00877A" },
        flag: { 400: "#FF5E7E", 500: "#FC2B6D" },
        amber: { 400: "#FBBF24" },
        // Sleeper position colors. Always paired with the position text, never color alone.
        pos: { qb: "#FC2B6D", rb: "#20CEB8", wr: "#56C9F8", te: "#FEAE58" },
      },
      fontFamily: {
        display: ['"Inter"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"Geist Mono"', "ui-monospace", "monospace"],
      },
      keyframes: {
        rise: { from: { opacity: "0" }, to: { opacity: "1" } },
        shimmer: { "100%": { transform: "translateX(100%)" } },
      },
      animation: {
        rise: "rise 0.15s ease-out both",
        shimmer: "shimmer 1.4s infinite",
      },
    },
  },
  plugins: [],
};
