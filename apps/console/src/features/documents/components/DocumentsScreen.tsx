import { useState } from "react";

import { useProject } from "@/features/projects";
import { ErrorState } from "@/components/ui/ErrorState";
import type { SourceDocument } from "@/types/documents";
import { REINDEXING } from "@/types/projects";

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

  return (
    <section className="max-w-3xl space-y-4">
      <header className="space-y-1">
        <h2 className="text-sm font-medium">Lore</h2>
        <p className="text-sm text-muted-foreground">
          What NPCs in this project can cite. Uploads are indexed in the background.
        </p>
      </header>

      {/*
        Two sources, because neither alone covers the window. The rows are the
        live one and carry both edges; the project status is what a project with
        no documents at all has to fall back on, and what is already true at
        mount.
      */}
      {(project?.status === REINDEXING || hasReindexingDocument(documents)) && <ReindexBanner />}

      <UploadDropzone
        onUpload={(file) => upload.mutate(file)}
        isUploading={upload.isPending}
        error={upload.error}
      />

      {isPending && <p className="text-sm text-muted-foreground">Loading&hellip;</p>}
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
          remove.mutate(filename, { onSuccess: () => setPendingDelete(null) })
        }
      />
    </section>
  );
}
