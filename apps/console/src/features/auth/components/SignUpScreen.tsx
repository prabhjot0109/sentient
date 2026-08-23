import { AuthView } from "@neondatabase/neon-js/auth/react/ui";

import { AuthUIShell } from "./AuthUIShell";

export function SignUpScreen() {
  return (
    <AuthUIShell>
      <AuthView view="SIGN_UP" redirectTo="/app" />
    </AuthUIShell>
  );
}
