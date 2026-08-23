import { useState } from "react";

import type { CreatedApiKey } from "@/types/keys";

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

  return (
    <div className="max-w-2xl space-y-8 p-8">
      <header className="space-y-1">
        <h1 className="text-xl font-semibold">API keys</h1>
        <p className="text-sm text-muted-foreground">
          One key authenticates the game. Keys belong to your account, not to a single project — the
          project is named separately in the URL below.
        </p>
      </header>

      <section className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-base font-semibold">Your keys</h2>
          <NewKeyDialog
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
    </div>
  );
}
