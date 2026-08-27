import { useState } from "react";

import { Button } from "@/components/ui/Button";
import type { ApiKey } from "@/types/keys";

import { useKeys } from "../hooks";
import { RevokeKeyDialog } from "./RevokeKeyDialog";
import { ErrorState } from "@/components/ui/ErrorState";

/** Never shows a key, not even masked: list_api_keys returns no key material. */
function KeyRow({ apiKey }: { apiKey: ApiKey }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <li className="flex items-center justify-between gap-4 border-b border-border py-2 last:border-b-0">
      <div className="min-w-0">
        <p className="truncate text-sm">
          {apiKey.label ?? <span className="text-muted-foreground">no label</span>}
          {apiKey.revoked && <span className="ml-2 text-xs text-destructive">revoked</span>}
        </p>
        {apiKey.created_at && (
          <p className="text-xs text-muted-foreground">
            created {new Date(apiKey.created_at).toLocaleDateString()}
          </p>
        )}
      </div>

      {!apiKey.revoked && (
        <Button size="sm" onClick={() => setConfirming(true)}>
          Revoke
        </Button>
      )}

      <RevokeKeyDialog apiKey={apiKey} open={confirming} onClose={() => setConfirming(false)} />
    </li>
  );
}

export function KeyList() {
  const { data: keys, isPending, error } = useKeys();

  if (isPending) return <p className="text-sm text-muted-foreground">Loading keys…</p>;
  if (error) return <ErrorState error={error} />;
  if (!keys.length) return <p className="text-sm text-muted-foreground">No keys yet.</p>;

  return (
    <ul>
      {keys.map((apiKey) => (
        <KeyRow key={apiKey.id} apiKey={apiKey} />
      ))}
    </ul>
  );
}
