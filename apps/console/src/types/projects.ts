/** A row of the backend's `projects` table, as `GET /v1/projects` returns it. */
export type Project = {
  id: string;
  user_id: string;
  name: string;
  base_preset: string;
  status: string;
  created_at: string | null;
};
