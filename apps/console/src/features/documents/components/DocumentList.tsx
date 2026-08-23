import type { SourceDocument } from "@/types/documents";

import { DocumentRow } from "./DocumentRow";

export function DocumentList({
  documents,
  onDelete,
}: {
  documents: SourceDocument[];
  onDelete: (document: SourceDocument) => void;
}) {
  return (
    <ul className="rounded-md border border-border px-4">
      {documents.map((document) => (
        <DocumentRow key={document.id} document={document} onDelete={onDelete} />
      ))}
    </ul>
  );
}
