import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/keys";

export const keyKeys = { all: ["keys"] as const };

export const useKeysQuery = () => useQuery({ queryKey: keyKeys.all, queryFn: api.listKeys });

export const useCreateKeyMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (label: string | null) => api.createKey(label),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keyKeys.all }),
  });
};

export const useRevokeKeyMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (keyId: string) => api.revokeKey(keyId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: keyKeys.all }),
  });
};
