import type { Project } from "@/types/projects";

import { apiFetch } from "./client";

export type ListProjectsResponse = { projects: Project[] };

/**
 * Authenticated. F1 uses it as the proof that the seam sends a token the backend
 * accepts; F2 builds the projects screen on it.
 */
export const listProjects = () => apiFetch<ListProjectsResponse>("/v1/projects");
