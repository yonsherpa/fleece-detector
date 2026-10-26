import { readFileSync } from "node:fs";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

/**
 * The production security headers live only in vercel.json. `npm run preview` serves the built
 * site with those same headers, so the Content Security Policy can be tested locally before deploying.
 * Locally the API is http://localhost:8000 instead of Render, and there's no HTTPS to upgrade to.
 */
function previewSecurityHeaders(): Record<string, string> {
  const vercel = JSON.parse(readFileSync(new URL("./vercel.json", import.meta.url), "utf-8"));
  const headers: Record<string, string> = {};
  for (const { key, value } of vercel.headers[0].headers as { key: string; value: string }[]) {
    headers[key] =
      key === "Content-Security-Policy"
        ? value.replace("https://*.onrender.com", "http://localhost:8000").replace("; upgrade-insecure-requests", "")
        : value;
  }
  return headers;
}

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  preview: { port: 5173, headers: previewSecurityHeaders() },
  build: {
    sourcemap: false, // don't publish source maps alongside the built site
    rollupOptions: {
      // Split big, rarely-changing libraries into their own cacheable files.
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          charts: ["recharts"],
        },
      },
    },
  },
});
