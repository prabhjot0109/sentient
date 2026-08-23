export function ReindexBanner() {
  return (
    <div className="rounded-md border border-amber-500/30 bg-amber-500/10 p-4 text-sm">
      <p className="font-medium text-amber-700">Re-embedding this project&rsquo;s lore</p>
      <p className="mt-1 text-amber-700/80">
        You changed a setting that alters the embedding space, so every document is being indexed
        again. NPCs answer <strong>409</strong> until it finishes. This page updates itself; you do
        not need to reload.
      </p>
    </div>
  );
}
