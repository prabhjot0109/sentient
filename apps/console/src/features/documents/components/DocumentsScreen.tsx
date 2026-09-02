import { useState } from "react";

import { ErrorState } from "@/components/ui/ErrorState";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { useProject } from "@/features/projects";
import type { SourceDocument } from "@/types/documents";
import { REINDEXING } from "@/types/projects";

import { describeBatch } from "../batch";
import { useDeleteDocument, useDocuments, useUploadDocument } from "../hooks";
import { hasReindexingDocument } from "../polling";
import { DeleteDocumentDialog } from "./DeleteDocumentDialog";
import { DocumentList } from "./DocumentList";
import { DocumentsEmptyState } from "./DocumentsEmptyState";
import { ReindexBanner } from "./ReindexBanner";
import { UploadDropzone } from "./UploadDropzone";

/**
 * Holds the state that spans the uploader, the list and the delete dialog.
 * `routes/` may not hold domain state, which is the same reason `KeysScreen`
 * exists.
 */
export function DocumentsScreen({ projectId }: { projectId: string }) {
  const { data: project } = useProject(projectId);
  const { data: documents, isPending, error } = useDocuments(projectId);
  const upload = useUploadDocument(projectId);
  const remove = useDeleteDocument(projectId);
  const [pendingDelete, setPendingDelete] = useState<SourceDocument | null>(null);
  const toast = useToast();

  const ready = documents?.filter((document) => document.status === "ready") ?? [];
  const chunks = ready.reduce((total, document) => total + document.chunk_count, 0);

  return (
    <section className="space-y-5">
      <header className="space-y-1">
        <h2 className="text-base font-semibold">Lore</h2>
        <p className="text-sm text-muted-foreground">
          What NPCs in this project can cite. Uploads are indexed in the background.
          {/*
            The retrievable total, inline rather than in a stat tile. It answers
            the question this page is actually opened to answer -- "is my lore in
            there?" -- and a number that only counts READY rows is the honest one:
            a processing row is not retrievable yet.
          */}
          {ready.length > 0 && (
            <>
              {" "}
              <span className="text-foreground">
                {chunks.toLocaleString()} chunks across {ready.length}{" "}
                {ready.length === 1 ? "file" : "files"}
              </span>{" "}
              are searchable now.
            </>
          )}
        </p>
      </header>

      {/*
        Two sources, because neither alone covers the window. The rows are the
        live one and carry both edges; the project status is what a project with
        no documents at all has to fall back on, and what is already true at
        mount.
      */}
      {/*
        `reindex_error` is checked FIRST and on its own. A failed rebuild leaves
        no `reindexing` rows and the project at `reindexing_required`, which is
        indistinguishable from a queued one by status alone -- the reason is the
        only thing that separates them, so it also has to be able to raise the
        banner by itself.
      */}
      {(project?.reindex_error ||
        project?.status === REINDEXING ||
        hasReindexingDocument(documents)) && <ReindexBanner reason={project?.reindex_error} />}

      <UploadDropzone
        onUpload={(files) =>
          upload.mutate(files, {
            // The 202 returns no document id and the row appears only on the next
            // poll, so without this the drop is followed by a visible pause in
            // which nothing at all has happened.
            //
            // The tone is read off the result, not assumed: a batch where some
            // files were rejected succeeded partially, and saying "Uploading 3
            // files" over two silent rejections is the kind of lie a user only
            // discovers later, when the lore they expected is not there.
            onSuccess: (result) =>
              toast({
                tone: result.failed.length > 0 ? "failure" : "success",
                ...describeBatch(result),
              }),
          })
        }
        isUploading={upload.isPending}
        error={upload.error}
      />

      {isPending && <SkeletonRows rows={3} className="h-14" />}
      {error && <ErrorState error={error} />}
      {documents &&
        (documents.length === 0 ? (
          <DocumentsEmptyState />
        ) : (
          <DocumentList documents={documents} onDelete={setPendingDelete} />
        ))}

      <DeleteDocumentDialog
        // Remounts on every open and close, which is what resets the typed
        // confirmation. See the dialog's own comment.
        key={pendingDelete?.filename ?? "closed"}
        document={pendingDelete}
        isPending={remove.isPending}
        error={remove.error}
        onClose={() => {
          // Without the reset a failed delete leaves `remove.error` set, and the
          // next dialog shows the previous file's error before you touch it.
          setPendingDelete(null);
          remove.reset();
        }}
        onConfirm={(filename) =>
          remove.mutate(filename, {
            onSuccess: () => {
              setPendingDelete(null);
              toast({
                tone: "success",
                title: `Deleted ${filename}`,
                body: "NPCs in this project can no longer cite it.",
              });
            },
          })
        }
      />
    </section>
  );
}
