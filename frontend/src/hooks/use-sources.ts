import { useState, useCallback, useEffect } from "react";
import { getSources, uploadFile, deleteSource } from "@/lib/api";
import type { Source } from "@/types";

export function useSources() {
  const [sources, setSources] = useState<Source[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSources = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await getSources();
      setSources(response.sources);
    } catch (err) {
      const errorMessage =
        err instanceof Error ? err.message : "Failed to fetch sources";
      setError(errorMessage);
    } finally {
      setIsLoading(false);
    }
  }, []);

  const upload = useCallback(
    async (file: File) => {
      setIsUploading(true);
      setError(null);

      try {
        await uploadFile(file);
        await fetchSources();
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to upload file";
        setError(errorMessage);
        throw err;
      } finally {
        setIsUploading(false);
      }
    },
    [fetchSources]
  );

  const remove = useCallback(
    async (filename: string) => {
      setError(null);

      try {
        await deleteSource(filename);
        await fetchSources();
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to delete file";
        setError(errorMessage);
        throw err;
      }
    },
    [fetchSources]
  );

  useEffect(() => {
    fetchSources();
  }, [fetchSources]);

  return {
    sources,
    isLoading,
    isUploading,
    error,
    fetchSources,
    upload,
    remove,
  };
}
