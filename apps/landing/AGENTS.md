# apps/landing

The public marketing site. TanStack Start + React 19 + Tailwind 4 + shadcn/ui,
built by Vite, output targeted at Cloudflare Workers via nitro.

**Read the repo root `AGENTS.md` / `CLAUDE.md` first.** This file only covers what is
specific to this app; the backend layer rule, the §7.1 import rule and the test gates
do not apply here, and nothing in this directory can affect them — the CI gates are
path-scoped to `src/` and `tests/`.

## State: deliberately unwired

The "Launch" call to action is a **plain link**, not an auth flow. This site has no
signed-in state and never reads a session: the user authenticates *inside*
`apps/web` after arriving. That is what lets the two apps stay separate builds with
no cross-origin token handoff. If a requirement ever appears to show signed-in state
here (a "Welcome back" header, an avatar), that assumption breaks and the two apps
should be reconsidered as one.

Wiring Launch → auth → app is Phase F work (**F1** auth shell, **F10** build/serve and
`CORS_ALLOW_ORIGINS`). Both are gated behind V2/V3. Do not build it here ahead of that.

## Commands

```bash
npm install        # npm, not bun -- package-lock.json is the lockfile of record
npm run dev
npm run build      # must stay green
npm run lint       # eslint + prettier; 0 errors expected
npm run format     # prettier --write
```

## Conventions

- **Routing is file-based** under `src/routes/`. Read `src/routes/README.md` before
  adding one — Next.js/Remix conventions (`src/pages/`, `app/layout.tsx`) are wrong here.
- **`vite.config.ts` is thin on purpose.** `@lovable.dev/vite-tanstack-config` already
  supplies tanstackStart, viteReact, tailwindcss, tsConfigPaths and nitro. Adding any of
  them manually duplicates the plugin and breaks the build.
- **Only the shadcn components in use are vendored** (9 of them). The unused 37 that came
  with the scaffold were deleted. `components.json` is retained, so add one back on demand
  with `npx shadcn@latest add <name>` rather than restoring the whole set.
- Page sections live in `src/components/sentient/`; `src/components/ui/` is vendored shadcn
  and should be edited sparingly.

## Known issues

- `src/assets/games/*.mp4.asset.json` are Lovable CDN pointers (`/__l5e/assets-v1/...`),
  not files in this repo. Outside Lovable's host those URLs 404 and the hero falls back to
  the `.jpg` posters. Either download the eight clips into `public/` or drop the video
  layer before deploying.
- `@lovable.dev/vite-tanstack-config` and `src/lib/lovable-error-reporting.ts` are
  platform lock-in. The reporter is inert off-platform (it no-ops when
  `window.__lovableEvents` is absent), so it is harmless but dead. Replacing the config
  package means writing the plugin list out by hand — a real migration, not a cleanup.
