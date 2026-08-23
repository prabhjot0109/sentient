import { useCreateKeyMutation, useKeysQuery, useRevokeKeyMutation } from "./api";

export const useKeys = useKeysQuery;
export const useCreateKey = useCreateKeyMutation;
export const useRevokeKey = useRevokeKeyMutation;
