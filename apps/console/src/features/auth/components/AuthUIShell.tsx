import { NeonAuthUIProvider } from "@neondatabase/neon-js/auth/react/ui";
import type { ReactNode } from "react";

import { authClient } from "@/lib/auth";

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
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
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
