import { useDeleteDocumentMutation, useDocumentsQuery, useUploadDocumentMutation } from "./api";

/**
 * The feature's public verbs. Components call these; they never call api.ts
 * directly, and they never reach lib/api at all.
 */
export const useDocuments = useDocumentsQuery;
export const useUploadDocument = useUploadDocumentMutation;
export const useDeleteDocument = useDeleteDocumentMutation;
