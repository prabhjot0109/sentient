import { useMutation, useQueryClient } from "@tanstack/react-query";

import { documentKeys } from "@/features/documents";
import { projectKeys } from "@/features/projects";
import type { ConfigPatch } from "@/lib/api/config";
import * as api from "@/lib/api/config";

/**
 * There is no query here. The config and the persona both arrive on
 * `GET /v1/projects/{id}`, which `features/projects` already owns -- a second
 * query for the same bytes would give two caches that disagree after a save.
 * These mutations invalidate the project's detail key instead.
 *
 * `projectKeys` is imported from `features/projects`' index.ts, which already
 * exports it. That is the allowed direction (a sibling feature through its public
 * surface, never its internals), and it is why this file does not rebuild
 * `["projects", id]` by hand -- two call sites spelling one key slightly
 * differently is the bug the factory exists to prevent.
 */
export const useUpdateConfigMutation = (projectId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: ConfigPatch) => api.updateConfig(projectId, patch),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) });
      // An embedding change flips the project to reindexing_required and walks
      // every document to `reindexing`, and both lists render status. The
      // documents query is the one that can actually SEE the window -- it polls,
      // and the project detail does not -- so it is invalidated too, which starts
      // its backoff from a fresh row rather than waiting out the current interval.
      queryClient.invalidateQueries({ queryKey: projectKeys.all });
      queryClient.invalidateQueries({ queryKey: documentKeys.all(projectId) });
    },
  });
};

export const useSetPersonaMutation = (projectId: string) => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (systemPrompt: string) => api.setPersona(projectId, systemPrompt),
    // The response is the stored config row, not the project detail -- it carries
    // no `persona_source`, so the editor's "inherited from the preset" note can
    // only be corrected by refetching the detail.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: projectKeys.detail(projectId) }),
  });
};
