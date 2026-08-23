import { Navigate } from "@tanstack/react-router";
import type { ReactNode } from "react";

import { useSession } from "../hooks";

export function RequireSession({ children }: { children: ReactNode }) {
  const { data, isPending } = useSession();

  // Three states, not two. Rendering the redirect while the session is still
  // resolving bounces a signed-in user to the sign-in screen on every reload --
  // the single most common bug in this component.
  if (isPending) return <div className="p-8 text-sm opacity-60">Checking your session…</div>;
  if (!data) return <Navigate to="/auth/sign-in" />;
  return <>{children}</>;
}
