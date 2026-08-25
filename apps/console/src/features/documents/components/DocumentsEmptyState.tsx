import { EmptyState } from "@/components/ui/EmptyState";

/**
 * The 25 MB is `UPLOAD_MAX_BYTES`'s default (26_214_400). If that default changes
 * in core/config.py, this string moves in the same commit -- `.env.example` and
 * `README.md` are already required to.
 */
export function DocumentsEmptyState() {
  return (
    <EmptyState
      title="No lore yet"
      body="Until you upload something, this project is grounded in nothing — NPCs will answer from the model alone. PDF and TXT, up to 25 MB each."
    />
  );
}
