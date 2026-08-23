import { NeonAuthUIProvider } from "@neondatabase/neon-js/auth/react/ui";
import type { ReactNode } from "react";

import { authClient } from "@/lib/auth";

/**
 * The provider and centred frame both auth screens share. F11 restyles it.
 *
 * Screens render `AuthView`, not `SignInForm`/`SignUpForm`. Those are the inner
 * building blocks: they require a `localization` prop that `AuthView` supplies,
 * and they render neither the card, the title, nor the sign-in/sign-up switch.
 *
 * `navigate` / `replace` / `Link` are deliberately left at their defaults, which
 * set `window.location.href`. That makes the form's own links (sign up, forgot
 * password) full page loads. Wiring them to TanStack Router means passing an
 * arbitrary string to a `to` prop typed as a union of known routes, which needs
 * a cast; not worth it for F1. F11 owns it.
 *
 * better-auth-ui's default `basePath` is "/auth" and its default view paths are
 * "sign-in" and "sign-up", so its internal links already match this app's routes.
 */
export function AuthUIShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="w-full max-w-sm">
        <NeonAuthUIProvider authClient={authClient} redirectTo="/app">
          {children}
        </NeonAuthUIProvider>
      </div>
    </div>
  );
}
