import { useSetPersonaMutation, useUpdateConfigMutation } from "./api";

/**
 * The feature's public verbs. Components call these; they never call api.ts
 * directly, and they never reach lib/api at all.
 */
export const useUpdateConfig = useUpdateConfigMutation;
export const useSetPersona = useSetPersonaMutation;
