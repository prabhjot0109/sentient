import { useRecentUtterancesQuery, useTranscribeMutation } from "./api";

/** The feature's public verbs. Components never reach into lib/api themselves. */
export const useTranscribe = useTranscribeMutation;
export const useRecentUtterances = useRecentUtterancesQuery;
