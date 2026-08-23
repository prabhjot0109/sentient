import type { Project, ProjectDetail } from "@/types/projects";

import { apiFetch } from "./client";

/**
 * Unwrapped at the boundary. The backend wraps the list in `{"projects": [...]}`
 * because a bare top-level array is awkward to extend; every consumer here wants
 * the array, and unwrapping in one place beats each of them reaching for `.projects`.
 */
export const listProjects = () =>
  apiFetch<{ projects: Project[] }>("/v1/projects").then((r) => r.projects);

/** Depends on B2. Reports the config as stored and the persona as resolved. */
export const getProject = (projectId: string) =>
  apiFetch<ProjectDetail>(`/v1/projects/${projectId}`);

export const createProject = (name: string, basePreset: string) =>
  apiFetch<Project>("/v1/projects", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name, base_preset: basePreset }),
  });

export const renameProject = (projectId: string, name: string) =>
  apiFetch<Project>(`/v1/projects/${projectId}`, {
    method: "PATCH",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ name }),
  });

export const deleteProject = (projectId: string) =>
  apiFetch<{ deleted: boolean }>(`/v1/projects/${projectId}`, { method: "DELETE" });

/**
 * Unauthenticated on the backend (`GET /v1/presets` takes no `current_user`), but
 * routed through the seam anyway: a token it does not read costs nothing, and a
 * `skipAuth` here would be one more thing to reason about.
 */
export const listPresets = () =>
  apiFetch<{ presets: string[] }>("/v1/presets").then((r) => r.presets);
