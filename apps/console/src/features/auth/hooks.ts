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
