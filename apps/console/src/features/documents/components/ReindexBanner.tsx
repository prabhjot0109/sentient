import { describeReindexFailure } from "../../../lib/api/messages";

/**
 * Two banners, because `projects.status = "reindexing_required"` means two
 * different things and the user needs opposite reactions to them.
 *
 * With no `reason` a rebuild is in flight and finishes on its own; with one, the
 * last rebuild failed and the project is waiting on the user. Before
 * `projects.reindex_error` the backend could not tell them apart either, so the
 * console showed the optimistic copy in both cases -- a project that is about to
 * be fine, forever.
 */
export function ReindexBanner({ reason }: { reason?: string | null }) {
  const failure = describeReindexFailure(reason);

  if (failure) {
    return (
      <div className="rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm">
        <p className="font-medium text-destructive">{failure.title}</p>
        {/* The backend's own sentence. It names the files and the cause where it
            can, and generic copy over the top of it throws away the only part
            the reader can act on. */}
        <p className="mt-1 text-destructive/80">{failure.body}</p>
        <p className="mt-2 text-muted-foreground">
          Fix the cause above, then change a retrieval setting to queue the rebuild again. Nothing
          retries on its own.
        </p>
      </div>
    );
  }

  return (
    <div className="rounded-md border border-warning/30 bg-warning/10 p-4 text-sm">
      <p className="font-medium text-warning">Re-embedding this project&rsquo;s lore</p>
      <p className="mt-1 text-warning/80">
        You changed a setting that alters the embedding space, so every document is being indexed
        again. NPCs answer <strong>409</strong> until it finishes. This page updates itself; you do
        not need to reload.
      </p>
    </div>
  );
}
