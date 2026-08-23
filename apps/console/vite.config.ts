import { tanstackRouter } from "@tanstack/router-plugin/vite";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
// vitest/config, not vite: same defineConfig plus the `test` block below.
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [
    // Must run before the react plugin: it generates routeTree.gen.ts, which
    // main.tsx imports.
    tanstackRouter({ target: "react", autoCodeSplitting: true }),
    react(),
    tailwindcss(),
  ],
  // Resolves the "@/*" paths entry in tsconfig.json. Native since Vite 8, which
  // warns that the vite-tsconfig-paths plugin apps/landing still carries is now
  // redundant.
  resolve: { tsconfigPaths: true },
  // Vitest covers the fetch seam and (from F8) the SSE parser, nothing else.
  // Both are pure logic over web APIs Node already provides, so no jsdom.
  test: { environment: "node", globals: false },
  server: {
    // 127.0.0.1, never localhost: uvicorn binds IPv4 only and Windows resolves
    // localhost to ::1 first -- 208ms of wasted connect time per request,
    // invisible in the server's own logs.
    host: "127.0.0.1",
    port: 5175,
  },
});
