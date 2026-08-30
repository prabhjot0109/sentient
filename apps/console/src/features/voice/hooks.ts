import { useTranscribeMutation } from "./api";

/** The feature's public verb. Components never reach into lib/api themselves. */
export const useTranscribe = useTranscribeMutation;
