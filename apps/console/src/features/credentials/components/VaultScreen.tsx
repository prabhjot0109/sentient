import { useState } from "react";

import { ApiError, ServiceUnavailableError } from "@/lib/api/errors";

import { useCredentials, useDeleteCredential, useStoreCredential } from "../hooks";
import { AddCredentialDialog } from "./AddCredentialDialog";
import { CredentialList } from "./CredentialList";

const message = (error: unknown): string | null =>
  error instanceof ApiError ? error.detail : error ? "Something went wrong." : null;

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
    return (
      <div className="max-w-2xl rounded-md border border-border p-6">
        <h2 className="text-sm font-medium">The credential vault is not configured</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          This server has no <code>SENTIENT_SECRET_KEY</code>, so it cannot encrypt or read stored
          provider keys. Until it does, projects use whatever keys the server itself was started
          with.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">{error.detail}</p>
      </div>
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
      {error && <p className="text-sm text-destructive">{message(error)}</p>}
      {remove.error && <p className="text-sm text-destructive">{message(remove.error)}</p>}

      {credentials &&
        (credentials.length === 0 ? (
          <p className="rounded-md border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            No keys stored. Projects fall back to the keys this server was started with.
          </p>
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
        error={message(store.error)}
        onSubmit={(provider, apiKey) => store.mutateAsync({ provider, apiKey })}
      />
    </div>
  );
}
