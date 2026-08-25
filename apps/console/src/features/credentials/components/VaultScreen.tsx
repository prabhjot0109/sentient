import { useState } from "react";

import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorState } from "@/components/ui/ErrorState";
import { ServiceUnavailableError } from "@/lib/api/errors";

import { useCredentials, useDeleteCredential, useStoreCredential } from "../hooks";
import { AddCredentialDialog } from "./AddCredentialDialog";
import { CredentialList } from "./CredentialList";

export function VaultScreen() {
  const { data: credentials, error, isPending } = useCredentials();
  const store = useStoreCredential();
  const remove = useDeleteCredential();
  const [removing, setRemoving] = useState<string | null>(null);

  // The 503 is a STATE, not a failure. "The vault is not configured on this
  // server" and "you have no keys" lead to opposite next actions, and every one
  // of the three routes -- including this GET -- answers 503 when
  // SENTIENT_SECRET_KEY is unset. Measured on a server started without it: all
  // four calls returned 503 "credential vault is not configured", including a
  // POST with a deliberately invalid provider, because `store_credential` gates
  // on the vault before it validates anything else.
  if (error instanceof ServiceUnavailableError) {
    // Title and body come from describe() so the wording cannot drift from
    // every other 503, but the actionable half -- WHICH env var, and what
    // happens meanwhile -- is this screen's own and rides in `action`.
    return (
      <ErrorState
        error={error}
        size="page"
        action={
          <p className="text-sm text-muted-foreground">
            This server has no <code>SENTIENT_SECRET_KEY</code>, so it cannot encrypt or read stored
            provider keys. Until it does, projects use whatever keys the server itself was started
            with.
          </p>
        }
      />
    );
  }

  return (
    <div className="max-w-2xl space-y-4">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">Provider keys</h1>
        <p className="text-sm text-muted-foreground">
          Your own API keys, encrypted at rest. A project that names a provider uses your key for it
          instead of the server&rsquo;s. These are shared across all of your projects.
        </p>
      </header>

      {isPending && <p className="text-sm text-muted-foreground">Loading…</p>}
      {error && <ErrorState error={error} />}
      {remove.error && <ErrorState error={remove.error} />}

      {credentials &&
        (credentials.length === 0 ? (
          <EmptyState
            title="No keys stored"
            body="Projects fall back to the keys this server was started with."
          />
        ) : (
          <CredentialList
            credentials={credentials}
            deletingProvider={removing}
            onDelete={(provider) => {
              setRemoving(provider);
              remove.mutate(provider, { onSettled: () => setRemoving(null) });
            }}
          />
        ))}

      <AddCredentialDialog
        existingProviders={(credentials ?? []).map((c) => c.provider)}
        isPending={store.isPending}
        error={store.error}
        onSubmit={(provider, apiKey) => store.mutateAsync({ provider, apiKey })}
      />
    </div>
  );
}
