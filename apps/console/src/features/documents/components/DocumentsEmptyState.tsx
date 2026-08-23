/**
 * The 25 MB is `UPLOAD_MAX_BYTES`'s default (26_214_400). If that default changes
 * in core/config.py, this string moves in the same commit -- `.env.example` and
 * `README.md` are already required to.
 */
export function DocumentsEmptyState() {
  return (
    <div className="rounded-md border border-dashed border-border p-8 text-center">
      <p className="text-sm font-medium">No lore yet</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Until you upload something, this project is grounded in nothing &mdash; NPCs will answer
        from the model alone. PDF and TXT, up to 25 MB each.
      </p>
    </div>
  );
}
