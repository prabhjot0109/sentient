export interface RetrievedSource {
  content: string;
  source: string;
  page_label?: string;
  score?: number | null;
  chunk_id?: number | null;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  // Lore chunks the RAG layer retrieved for this answer (live only, not persisted).
  sources?: RetrievedSource[];
}

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  // Persisted alongside the message so source chips survive reloads.
  sources?: RetrievedSource[];
}

export interface Source {
  name: string;
  path: string;
  size: number;
}

export interface ChatSessionSummary {
  id: string;
  title: string;
  preview: string;
  createdAt: string;
  updatedAt: string;
  messageCount: number;
}

