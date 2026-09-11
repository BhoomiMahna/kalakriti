import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app calls the backend with RELATIVE paths (/api, /media) — no hardcoded
// hosts anywhere. In dev and local preview those are proxied to the FastAPI
// backend on :8000; in production Vercel rewrites (vercel.json) forward them to
// the deployed backend, so there are no localhost URLs and no CORS.
// Dev/preview proxy target. Defaults to the local backend; override to test the
// production build against a deployed backend, e.g.
//   VITE_PROXY_TARGET=https://kalakriti-backend-production.up.railway.app npm run preview
// (Production on Vercel does NOT use this — it uses the rewrites in vercel.json.)
const target = process.env.VITE_PROXY_TARGET || "http://localhost:8000";
const proxy = {
  "/api": { target, changeOrigin: true },
  "/media": { target, changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
});
