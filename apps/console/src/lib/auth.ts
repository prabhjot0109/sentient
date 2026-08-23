// Not exported from the main entry -- the /auth and /auth/react/adapters subpaths
// are required, and adapters are factory functions that must be called with ().
import { createInternalNeonAuth } from "@neondatabase/neon-js/auth";
import { BetterAuthReactAdapter } from "@neondatabase/neon-js/auth/react/adapters";

const authUrl = import.meta.env.VITE_NEON_AUTH_URL;

if (!authUrl) {
  // Fail loudly at boot rather than producing an unauthenticated client that
  // 401s on every request with no obvious cause.
  throw new Error(
    "VITE_NEON_AUTH_URL is not set. Run `neon env pull` at the repo root and copy " +
      "NEON_AUTH_BASE_URL into apps/console/.env.local.",
  );
}

/**
 * `createInternalNeonAuth`, not `createAuthClient`, and the name is misleading:
 * both are exported from the package's public entry and documented in the same
 * JSDoc block. `createAuthClient(url, cfg)` is literally
 * `createInternalNeonAuth(url, cfg).adapter` -- it returns the Better Auth client
 * and THROWS AWAY `getJWTToken`. Verified against @neondatabase/auth@0.5.0-beta:
 * `createAuthClient(...).getJWTToken` is a TS2339, and undefined at runtime.
 *
 * No `fetchOptions: { credentials: "include" }` either. It is not on the public
 * config type, and Better Auth's own client config already sets
 * `credentials: "include"` whenever the browser supports it.
 */
const neonAuth = createInternalNeonAuth(authUrl, {
  adapter: BetterAuthReactAdapter(),
});

/**
 * The Better Auth React client: `useSession()`, `signIn`, `signUp`, `signOut`.
 * This is what `NeonAuthUIProvider` wants for its `authClient` prop.
 */
export const authClient = neonAuth.adapter;

/**
 * The JWT the Sentient backend verifies against Neon's JWKS.
 *
 * This is NOT the session. The session is a cookie on the Neon Auth origin; this
 * is the bearer token minted from it. `lib/api/client.ts` is the only consumer --
 * it fetches one per request and re-reads on a 401.
 */
export async function getAccessToken(): Promise<string | null> {
  try {
    return await neonAuth.getJWTToken();
  } catch {
    // Signed out, or the session cookie expired. Not an error condition: the seam
    // sends the request unauthenticated and the backend answers 401, which is the
    // signal the guard already handles.
    return null;
  }
}
