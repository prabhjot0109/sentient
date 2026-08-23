import { ApiError } from "@/lib/api/errors";

import { useAuthProbe, useSession } from "../hooks";

/**
 * F1's whole visible payload: proof that the seam reaches the backend with a
 * token it accepts. F2 replaces this route with the projects screen.
 */
export function AuthProbe() {
  const { data: session } = useSession();
  const { data, error, isPending } = useAuthProbe();

  return (
    <div className="space-y-4 p-8">
      <h1 className="text-xl font-semibold">Signed in</h1>
      <p className="text-sm opacity-70">{session?.user.email}</p>

      {isPending && <p className="text-sm opacity-60">Asking the backend who you are…</p>}

      {error && (
        <p className="text-sm text-red-600">
          {error instanceof ApiError
            ? `${error.status} — ${error.detail}`
            : "The backend is unreachable. Is uvicorn running on 127.0.0.1:8000?"}
        </p>
      )}

      {data && (
        <p className="text-sm">
          <code>GET /v1/projects</code> returned 200 with {data.projects.length} project
          {data.projects.length === 1 ? "" : "s"}. The token was minted by Neon Auth, verified
          against its JWKS, and resolved to a mirrored <code>users</code> row.
        </p>
      )}
    </div>
  );
}
