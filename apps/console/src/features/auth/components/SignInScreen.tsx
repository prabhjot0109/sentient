import { AuthView } from "@neondatabase/neon-js/auth/react/ui";

import { AuthUIShell } from "./AuthUIShell";

export function SignInScreen() {
  return (
    <AuthUIShell>
      <AuthView view="SIGN_IN" redirectTo="/app" />
    </AuthUIShell>
  );
}
