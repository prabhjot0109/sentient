import { NeonAuthUIProvider } from "@neondatabase/neon-js/auth/react/ui";
import type { ReactNode } from "react";

import { authClient } from "@/lib/auth";

/**
 * Neon Auth trusts the literal hostname `localhost` and rejects an IP literal.
 * Measured against this branch's endpoint on 2026-08-28: `POST /sign-in/social`
 * with provider google answers 200 and a Google redirect from
 * `http://localhost:5175`, and 403 `INVALID_CALLBACKURL` from
 * `http://127.0.0.1:5175`. Email sign-up fails the same way with
 * `INVALID_ORIGIN`.
 *
 * The rule is already written down in AGENTS.md, with a table, and it still cost
 * a debugging session -- because the failure is SILENT. The SPA gets a 403 JSON
 * body, no redirect happens, and the button just does nothing. So it is a
 * runtime check now rather than another paragraph.
 *
 * Only in dev. A deployed origin is legitimately not localhost; it becomes
 * trusted through `neon neon-auth domain add <origin>` instead, and a banner
 * telling a production user to browse localhost would be nonsense.
 */
function localhostToUseInstead(): string | null {
  if (!import.meta.env.DEV) return null;
  const { hostname, port } = window.location;
  if (hostname === "localhost") return null;
  return `http://localhost:${port || "5175"}`;
}

/**
 * The provider and centred frame both auth screens share.
 *
 * F11 restyled AuthView without touching this file or forking the component.
 * @neondatabase/neon-js writes its theme as `--neon-background: var(--background,
 * <its default>)`, so defining --background and friends in styles/tokens.css
 * reaches the prebuilt auth UI too.
 *
 * Screens render `AuthView`, not `SignInForm`/`SignUpForm`. Those are the inner
 * building blocks: they require a `localization` prop that `AuthView` supplies,
 * and they render neither the card, the title, nor the sign-in/sign-up switch.
 *
 * `navigate` / `replace` / `Link` are deliberately left at their defaults, which
 * set `window.location.href`. That makes the form's own links (sign up, forgot
 * password) full page loads. Wiring them to TanStack Router means passing an
 * arbitrary string to a `to` prop typed as a union of known routes, which needs
 * a cast. Still open.
 *
 * better-auth-ui's default `basePath` is "/auth" and its default view paths are
 * "sign-in" and "sign-up", so its internal links already match this app's routes.
 */
export function AuthUIShell({ children }: { children: ReactNode }) {
  const shouldBrowseAt = localhostToUseInstead();

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        {shouldBrowseAt && (
          <p
            role="alert"
            className="mb-4 rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-sm"
          >
            Sign-in cannot work on <span className="font-mono">{window.location.hostname}</span>.
            Neon Auth only trusts <span className="font-mono">localhost</span> in development and
            rejects an IP address, so Google and email both fail with no visible error. Open{" "}
            <a className="underline underline-offset-4" href={shouldBrowseAt}>
              {shouldBrowseAt}
            </a>{" "}
            instead.
          </p>
        )}
        <NeonAuthUIProvider
          authClient={authClient}
          redirectTo="/app"
          /*
           * Renders "Continue with Google" above the email form, on BOTH views,
           * because AuthView shares one provider. `social` passes straight
           * through: NeonAuthUIProviderProps is
           * `Omit<AuthUIProviderProps, "authClient"> & {...}`, so every
           * better-auth-ui option including this one is already accepted.
           *
           * The provider must also exist on the Neon side or the button 400s.
           * It does: `neon neon-auth oauth-provider list --branch dev-console`
           * reports `google  shared` -- Neon's SHARED OAuth app, which needs no
           * Google Cloud project and no client secret anywhere in .env. That is
           * why nothing here reads a key.
           *
           * Shared is DEV ONLY. It shows Neon's own branding on the consent
           * screen, and Neon says not to ship it. Production swaps in your own
           * client: see "Google sign-in" in the repo README / .env.example.
           */
          social={{ providers: ["google"] }}
        >
          {children}
        </NeonAuthUIProvider>
      </div>
    </div>
  );
}
