import { Trash2 } from "lucide-react";

import { Menu } from "@/components/ui/Menu";
import type { StoredCredential } from "@/types/credentials";

export function CredentialList({
  credentials,
  onDelete,
  deletingProvider,
}: {
  credentials: StoredCredential[];
  onDelete: (provider: string) => void;
  deletingProvider: string | null;
}) {
  return (
    <ul className="rounded-lg border border-border px-4">
      {credentials.map((credential) => (
        <li
          key={credential.provider}
          className="flex items-center gap-3 border-b border-border py-3 last:border-0"
        >
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{credential.provider}</p>
            {/*
              key_hint is all the server has. There is no reveal, because the vault
              stores ciphertext and no route returns plaintext -- the promise is
              that the key never leaves, and a "show" button would be a lie.

              Rendered RAW. `core/crypto.key_hint` is `"…" + raw[-4:]`, so the
              ellipsis is already in the value; the F3+F4 plan's `…{key_hint}`
              would have printed `……ABCD`. Measured against the live vault.
            */}
            <p className="font-mono mt-0.5 text-xs text-muted-foreground">
              {credential.key_hint ?? "stored"}
            </p>
          </div>
          {deletingProvider === credential.provider ? (
            <span className="px-2 text-xs text-muted-foreground">Removing…</span>
          ) : (
            <Menu
              label={`Actions for the ${credential.provider} key`}
              items={[
                {
                  label: "Remove this key",
                  icon: Trash2,
                  danger: true,
                  onSelect: () => onDelete(credential.provider),
                },
              ]}
            />
          )}
        </li>
      ))}
    </ul>
  );
}
