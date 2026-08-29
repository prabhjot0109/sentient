import { Ban } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { Menu } from "@/components/ui/Menu";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { absoluteTime, relativeTime } from "@/lib/time";
import type { ApiKey } from "@/types/keys";

import { useKeys } from "../hooks";
import { RevokeKeyDialog } from "./RevokeKeyDialog";

/** Never shows a key, not even masked: `list_api_keys` returns no key material. */
function KeyRow({ apiKey }: { apiKey: ApiKey }) {
  const [confirming, setConfirming] = useState(false);

  return (
    <li className="flex items-center gap-3 border-b border-border py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="flex items-center gap-2 text-sm">
          <span className="truncate font-medium">
            {apiKey.label ?? <span className="text-muted-foreground italic">Unlabelled</span>}
          </span>
          {apiKey.revoked && <Badge tone="danger">Revoked</Badge>}
        </p>
        {apiKey.created_at && (
          <p className="mt-0.5 text-xs text-muted-foreground">
            Created{" "}
            <time dateTime={apiKey.created_at} title={absoluteTime(apiKey.created_at)}>
              {relativeTime(apiKey.created_at)}
            </time>
          </p>
        )}
      </div>

      {/*
        A menu rather than the full-width "Revoke" button this row used to carry.
        Revoking is irreversible and stops a running game mid-sentence; giving it
        the same weight as a primary action on every row is how it gets pressed by
        someone aiming for the row itself.
      */}
      {!apiKey.revoked && (
        <Menu
          label={`Actions for ${apiKey.label ?? "this key"}`}
          items={[
            { label: "Revoke", icon: Ban, danger: true, onSelect: () => setConfirming(true) },
          ]}
        />
      )}

      <RevokeKeyDialog apiKey={apiKey} open={confirming} onClose={() => setConfirming(false)} />
    </li>
  );
}

export function KeyList() {
  const { data, isPending, error } = useKeys();
  const [showRevoked, setShowRevoked] = useState(false);

  if (isPending) return <SkeletonRows rows={2} className="h-12" />;
  if (error) return <ErrorState error={error} />;

  /*
   * Split, not sorted. A revoked key is not a lesser live key -- it authenticates
   * nothing, and its only remaining job is to be a record that it once existed.
   * Interleaved by date, the two kinds read as one list where some rows happen to
   * carry a red pill, and the count above the list stops matching what is under
   * it.
   */
  const live = data.keys.filter((key) => !key.revoked);
  const revoked = data.keys.filter((key) => key.revoked);

  if (data.keys.length === 0) {
    return (
      <EmptyState
        title="No keys yet"
        body="A key is what lets Mantella reach this server. Create one, then paste the URL below into the game."
      />
    );
  }

  return (
    <div className="space-y-3">
      {live.length > 0 ? (
        <ul>
          {live.map((apiKey) => (
            <KeyRow key={apiKey.id} apiKey={apiKey} />
          ))}
        </ul>
      ) : (
        <EmptyState
          title="Every key is revoked"
          body="Nothing can authenticate to this account right now. Create a key to reconnect the game."
        />
      )}

      {revoked.length > 0 && (
        <div>
          <button
            type="button"
            onClick={() => setShowRevoked((open) => !open)}
            aria-expanded={showRevoked}
            className="rounded text-xs text-muted-foreground underline-offset-4 transition-colors hover:text-foreground hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
          >
            {showRevoked ? "Hide" : "Show"} {revoked.length} revoked{" "}
            {revoked.length === 1 ? "key" : "keys"}
          </button>
          {showRevoked && (
            <ul className="mt-1 opacity-60">
              {revoked.map((apiKey) => (
                <KeyRow key={apiKey.id} apiKey={apiKey} />
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
