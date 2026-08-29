import { useState } from "react";

import { PageColumn } from "@/components/shell/PageColumn";
import type { CreatedApiKey } from "@/types/keys";

import { useKeys } from "../hooks";
import { KeyList } from "./KeyList";
import { MantellaSetupCard } from "./MantellaSetupCard";
import { NewKeyDialog } from "./NewKeyDialog";
import { RevealedKey } from "./RevealedKey";

/**
 * Owns the one thing that cannot live anywhere else: the raw key, which exists
 * only in this tab's memory between the POST that minted it and the next reload.
 * The reveal dialog and the Mantella URL both need it, and a route may not hold
 * domain state, so the feature owns it here.
 */
export function KeysScreen() {
  const [created, setCreated] = useState<CreatedApiKey | null>(null);
  const [revealing, setRevealing] = useState(false);
  const { data } = useKeys();

  const live = data?.keys.filter((key) => !key.revoked).length ?? 0;
  // 0 is the uncapped sentinel on both sides of the wire, so `atCap` must never
  // be `live >= limit` alone -- that is true for every user on an uncapped server.
  const limit = data?.limit ?? 0;
  const atCap = limit > 0 && live >= limit;

  return (
    <PageColumn className="space-y-10 py-10">
      <header className="space-y-2">
        <h1 className="font-display text-2xl font-semibold tracking-tight">API keys</h1>
        <p className="max-w-prose text-sm text-muted-foreground">
          One key authenticates the game. Keys belong to your account, not to a single project — the
          project is named separately in the URL below.
        </p>
      </header>

      <section className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold">Your keys</h2>
            {/*
              The ceiling, before it is hit. `MAX_API_KEYS_PER_USER` answers 409
              on the 26th key, and until the list route reported `limit` the only
              way to learn the cap existed was to run into it -- which reads as a
              bug the first time rather than as a limit.
            */}
            <p className="mt-0.5 text-xs text-muted-foreground">
              {limit > 0 ? `${live} of ${limit} active` : `${live} active`}
            </p>
          </div>
          <NewKeyDialog
            atCap={atCap}
            limit={limit}
            onCreated={(key) => {
              setCreated(key);
              setRevealing(true);
            }}
          />
        </div>
        <KeyList />
      </section>

      <MantellaSetupCard created={created} />

      {created && revealing && (
        <RevealedKey created={created} onDismiss={() => setRevealing(false)} />
      )}
    </PageColumn>
  );
}
