/**
 * Refuse a Vercel build that would ship a broken Get Started button.
 *
 * `src/lib/site.ts` falls back to `http://localhost:5175/auth/sign-up` when
 * VITE_CONSOLE_URL is unset. That fallback is right for development and wrong for
 * every deployed build, and on 2026-09-01 it reached production: the variable was
 * set on the console's Vercel project and not the landing one, so the live site
 * sent every visitor to a port on their own machine. The build passed, the page
 * rendered, and the only symptom was the click.
 *
 * This runs BEFORE `vite build` because Vite inlines the value into the bundle.
 * Once the bundle exists the wrong string is already compiled in, and no runtime
 * check can distinguish "localhost was chosen" from "localhost was a fallback".
 * Build time is the last moment the mistake is cheap.
 *
 * Scoped to Vercel by the VERCEL variable, which Vercel sets on its build
 * machines and nothing else does. CI builds this app with no environment at all
 * and must stay green: CI asks whether it compiles, Vercel asks whether it is fit
 * to serve. `process.env` rather than `import.meta.env` because this is Node
 * before the bundler, where the VITE_ prefix filter does not apply.
 */

const REQUIRED = [
  {
    key: "VITE_CONSOLE_URL",
    what: "the console origin plus /auth/sign-up",
    breaks: "the Get Started button points at localhost and goes nowhere",
  },
];

if (!process.env.VERCEL) {
  process.exit(0);
}

const missing = REQUIRED.filter(({ key }) => !process.env[key]);

if (missing.length > 0) {
  const lines = missing.map(
    ({ key, what, breaks }) => `  ${key} — ${what}\n      Without it, ${breaks}.`,
  );
  console.error(
    [
      "",
      "This Vercel build is missing environment variables it cannot work without:",
      "",
      ...lines,
      "",
      "Set them on THIS Vercel project (Settings → Environment Variables), type",
      "Config rather than Secret since they are compiled into a public bundle, and",
      "tick every environment — Preview inherits nothing from Production. Then",
      "redeploy: saving a variable does not rebuild anything.",
      "",
    ].join("\n"),
  );
  process.exit(1);
}
