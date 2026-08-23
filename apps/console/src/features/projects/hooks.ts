import {
  useCreateProjectMutation,
  useDeleteProjectMutation,
  usePresetsQuery,
  useProjectQuery,
  useProjectsQuery,
  useRenameProjectMutation,
} from "./api";

/**
 * The feature's public verbs. Components call these; they never call api.ts
 * directly, and they never reach lib/api at all.
 */
export const useProjects = useProjectsQuery;
export const useProject = useProjectQuery;
export const usePresets = usePresetsQuery;
export const useCreateProject = useCreateProjectMutation;
export const useRenameProject = useRenameProjectMutation;
export const useDeleteProject = useDeleteProjectMutation;
