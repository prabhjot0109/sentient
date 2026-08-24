import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/credentials";

/**
 * User-level, not project-level: `provider_credentials` is UNIQUE(user_id,
 * provider) and has no `project_id`, so there is no id to key on here either.
 */
export const credentialKeys = { all: ["credentials"] as const };

export const useCredentialsQuery = () =>
  useQuery({
    queryKey: credentialKeys.all,
    queryFn: api.listCredentials,
    // A 503 means the vault is unconfigured on this server. Retrying will not
    // configure it, and three seconds of spinner delays a message the user needs.
    retry: false,
  });

export const useStoreCredentialMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ provider, apiKey }: { provider: string; apiKey: string }) =>
      api.storeCredential(provider, apiKey),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: credentialKeys.all }),
  });
};

export const useDeleteCredentialMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (provider: string) => api.deleteCredential(provider),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: credentialKeys.all }),
  });
};
