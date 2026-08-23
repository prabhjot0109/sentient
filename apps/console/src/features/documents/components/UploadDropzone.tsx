import { useRef, useState } from "react";

/**
 * The `accept` attribute is a hint the file picker honours and a drop does not,
 * so the backend's 400 "Only PDF and TXT files are supported" is still the real
 * gate. That is why `error` renders here rather than being assumed away.
 */
export function UploadDropzone({
  onUpload,
  isUploading,
  error,
}: {
  onUpload: (file: File) => void;
  isUploading: boolean;
  error: string | null;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [isOver, setIsOver] = useState(false);

  const take = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onUpload(file);
  };

  return (
    <div className="space-y-2">
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsOver(true);
        }}
        onDragLeave={() => setIsOver(false)}
        onDrop={(e) => {
          e.preventDefault();
          setIsOver(false);
          take(e.dataTransfer.files);
        }}
        className={`rounded-md border border-dashed p-6 text-center text-sm ${
          isOver ? "border-primary bg-primary/5" : "border-border"
        }`}
      >
        <p className="text-muted-foreground">
          Drop a PDF or TXT here, or{" "}
          <button
            type="button"
            onClick={() => inputRef.current?.click()}
            disabled={isUploading}
            className="text-foreground underline underline-offset-2 disabled:opacity-50"
          >
            choose a file
          </button>
          .
        </p>
        {/*
          No progress bar, deliberately. lib/api/client.ts is built on fetch, and
          fetch cannot report request-body progress; the only way to get it is
          XMLHttpRequest, which would bypass the seam that attaches the auth
          header, refreshes once on 401, and maps status onto typed errors. The
          slow leg is ingestion, and that IS reported -- by the polled status.
        */}
        {isUploading && <p className="mt-2 text-muted-foreground">Uploading&hellip;</p>}
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.txt"
          className="hidden"
          onChange={(e) => {
            take(e.target.files);
            // Reset, or picking the SAME file twice fires no change event and the
            // retry-after-a-failure case silently does nothing.
            e.target.value = "";
          }}
        />
      </div>
      {error && <p className="text-sm text-destructive">{error}</p>}
    </div>
  );
}
