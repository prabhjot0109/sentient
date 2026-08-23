import { useQuery } from "@tanstack/react-query";

import { listProjects } from "@/lib/api/projects";
import { authClient } from "@/lib/auth";

/**
 * The session is Neon Auth's, not ours: a cookie on the Neon Auth origin. It is
 * NOT the backend JWT -- that comes from getAccessToken() and lives entirely
 * inside the fetch seam. Confusing the two is how a signed-in UI ends up making
 * unauthenticated requests.
 */
export const useSession = () => authClient.useSession();

export const useSignOut = () => async () => {
  await authClient.signOut();
  // Full reload rather than a router navigation: it drops every cached query and
  // any in-flight stream, which is what "signed out" has to mean.
  window.location.href = "/auth/sign-in";
};

/**
 * F1's end-to-end proof, and nothing more. `GET /v1/projects` is authenticated,
 * so a 200 here means the seam attached a token, Neon's JWKS verified it, and
 * `ensure_user(sub)` resolved it to a mirrored `users` row. That chain is the V4
 * gate. `/health` cannot show any of it -- it is `skipAuth`.
 *
 * Delete this when F2 lands `features/projects` with a real `useProjects()`.
 */
export const useAuthProbe = () =>
  useQuery({
    queryKey: ["auth-probe", "projects"],
    queryFn: listProjects,
    retry: false,
  });
