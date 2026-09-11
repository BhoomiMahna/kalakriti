import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The app calls the backend with RELATIVE paths (/api, /media) — no hardcoded
// hosts anywhere. In dev and local preview those are proxied to the FastAPI
// backend on :8000; in production Vercel rewrites (vercel.json) forward them to
// the deployed backend, so there are no localhost URLs and no CORS.
const proxy = {
  "/api": "http://localhost:8000",
  "/media": "http://localhost:8000",
};

export default defineConfig({
  plugins: [react()],
  base: "/",
  server: { port: 5173, proxy },
  preview: { port: 4173, proxy },
});
