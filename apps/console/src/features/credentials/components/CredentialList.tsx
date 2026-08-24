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
    <ul className="rounded-md border border-border px-4">
      {credentials.map((credential) => (
        <li
          key={credential.provider}
          className="flex items-center justify-between border-b border-border py-3 last:border-0"
        >
          <div>
            <p className="text-sm font-medium">{credential.provider}</p>
            {/*
              key_hint is all the server has. There is no reveal, because the vault
              stores ciphertext and no route returns plaintext -- the promise is
              that the key never leaves, and a "show" button would be a lie.

              Rendered RAW. `core/crypto.key_hint` is `"…" + raw[-4:]`, so the
              ellipsis is already in the value; the F3+F4 plan's `…{key_hint}`
              would have printed `……ABCD`. Measured against the live vault.
            */}
            <p className="text-xs text-muted-foreground">{credential.key_hint ?? "stored"}</p>
          </div>
          <button
            type="button"
            disabled={deletingProvider === credential.provider}
            onClick={() => onDelete(credential.provider)}
            className="text-xs text-muted-foreground hover:text-destructive disabled:opacity-50"
          >
            {deletingProvider === credential.provider ? "Removing…" : "Remove"}
          </button>
        </li>
      ))}
    </ul>
  );
}
