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
    // Bind BOTH stacks (::1 and 127.0.0.1), and browse this app over
    // http://localhost:5175.
    //
    // The repo rule is "127.0.0.1, never localhost", and it still holds for
    // VITE_API_BASE_URL -- uvicorn binds IPv4 only, so localhost costs 208ms per
    // request there. It cannot hold for THIS origin: Neon Auth trusts the literal
    // hostname `localhost` and rejects `http://127.0.0.1:<port>` with
    // INVALID_ORIGIN on every state-changing route, so sign-up and sign-in fail
    // outright when the page is served from the IP literal. Measured against the
    // live branch 2026-08-23.
    //
    // Binding 127.0.0.1 alone still "works" via the browser's ::1-then-IPv4
    // fallback, but pays that same 208ms on every dev module request (measured:
    // 216ms vs 9ms). Listening on both makes ::1 connect first try.
    host: true,
    port: 5175,
    strictPort: true,
  },
});
