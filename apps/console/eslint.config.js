import js from "@eslint/js";
import { defineConfig, globalIgnores } from "eslint/config";
import prettier from "eslint-config-prettier";
import reactHooks from "eslint-plugin-react-hooks";
import reactRefresh from "eslint-plugin-react-refresh";
import tseslint from "typescript-eslint";

// The one module allowed to call fetch. Everything else goes through it.
const FETCH_SEAM = "src/lib/api/**";

const noFetch = {
  "no-restricted-globals": [
    "error",
    {
      name: "fetch",
      message:
        "Go through lib/api. client.ts is the ONLY place the auth header, the 401 refresh, and error mapping live -- bypassing it silently loses all three.",
    },
  ],
  "no-restricted-properties": [
    "error",
    {
      object: "window",
      property: "fetch",
      message: "Go through lib/api. window.fetch bypasses the seam exactly as a bare fetch does.",
    },
    {
      object: "globalThis",
      property: "fetch",
      message:
        "Go through lib/api. globalThis.fetch bypasses the seam exactly as a bare fetch does.",
    },
  ],
};

export default defineConfig([
  globalIgnores(["dist", "src/routeTree.gen.ts"]),
  {
    files: ["**/*.{ts,tsx}"],
    extends: [js.configs.recommended, tseslint.configs.recommended],
    plugins: { "react-hooks": reactHooks, "react-refresh": reactRefresh },
    rules: { ...reactHooks.configs.recommended.rules },
  },

  // --- The layer contract. Dependencies point one way:
  // ---   routes -> features -> lib -> types
  // --- A violation is an architectural regression: move the code, do not
  // --- weaken the rule. This mirrors import-linter on the Python side.
  {
    files: ["src/components/ui/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["@/features/*", "../../features/*", "../features/*"],
              message:
                'components/ui is domain-free. A primitive that knows what a "project" is has stopped being a primitive.',
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/lib/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: [
                "@/features/*",
                "@/routes/*",
                "@/components/*",
                "../../features/*",
                "../../routes/*",
                "../../components/*",
              ],
              message: "lib is the bottom layer. Nothing above it may be imported here.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["src/features/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              // Sibling features are reachable only through their index.ts.
              // Cross-feature reaching is how a modular tree becomes a graph.
              group: ["@/features/*/*"],
              message:
                "Import a sibling feature through its index.ts only. Anything two features share moves DOWN into lib/ or components/ui/, never sideways.",
            },
            {
              group: ["@/routes/*"],
              message: "Features must not import routes.",
            },
          ],
        },
      ],
    },
  },

  // The one rule a boundary linter cannot express: the fetch seam. Stated once
  // as the invariant actually is -- exactly one module may call fetch -- rather
  // than re-listed per layer, so a layer added later is covered by default.
  {
    files: ["src/**/*.{ts,tsx}"],
    ignores: [FETCH_SEAM],
    rules: noFetch,
  },

  prettier,
]);
