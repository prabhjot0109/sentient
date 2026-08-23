import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import * as api from "@/lib/api/projects";

/**
 * One factory, so no two call sites can invalidate slightly different keys. That
 * bug presents as "the sidebar didn't update" and costs an hour to find.
 */
export const projectKeys = {
  all: ["projects"] as const,
  detail: (id: string) => ["projects", id] as const,
  presets: ["presets"] as const,
};

export const useProjectsQuery = () =>
  useQuery({ queryKey: projectKeys.all, queryFn: api.listProjects });

export const useProjectQuery = (projectId: string) =>
  useQuery({
    queryKey: projectKeys.detail(projectId),
    queryFn: () => api.getProject(projectId),
    // A 404 here means the project is not this user's, or does not exist. Neither
    // improves on a retry, and retrying turns a clean "not found" pane into three
    // seconds of spinner first.
    retry: false,
  });

export const usePresetsQuery = () =>
  useQuery({
    queryKey: projectKeys.presets,
    queryFn: api.listPresets,
    // The preset list is a dict compiled into core/presets.py. Refetching it on
    // every window focus is pure noise.
    staleTime: Infinity,
  });

export const useCreateProjectMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ name, basePreset }: { name: string; basePreset: string }) =>
      api.createProject(name, basePreset),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.all }),
  });
};

export const useRenameProjectMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, name }: { id: string; name: string }) => api.renameProject(id, name),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(variables.id) });
    },
  });
};

export const useDeleteProjectMutation = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteProject(id),
    onSuccess: (_data, id) => {
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
      // The detail cache for a deleted project is not stale, it is wrong. Left in
      // place, navigating back to that id renders the dead project from cache
      // before the refetch 404s.
      queryClient.removeQueries({ queryKey: projectKeys.detail(id) });
    },
  });
};
