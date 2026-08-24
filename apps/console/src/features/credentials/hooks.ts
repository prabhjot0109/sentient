import {
  useCredentialsQuery,
  useDeleteCredentialMutation,
  useStoreCredentialMutation,
} from "./api";

/**
 * The feature's public verbs. Components call these; they never call api.ts
 * directly, and they never reach lib/api at all.
 */
export const useCredentials = useCredentialsQuery;
export const useStoreCredential = useStoreCredentialMutation;
export const useDeleteCredential = useDeleteCredentialMutation;
