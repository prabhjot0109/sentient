const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

import type { ChatSessionSummary, Source, StoredMessage } from "@/types";

export interface ChatResponse {
  response: string;
  success: boolean;
  sources?: Array<{
    content: string;
    score?: number | null;
    source: string;
    page_label?: string;
    chunk_id?: number | null;
  }>;
  top_k?: number | null;
  retrieval_ms?: number | null;
}

export interface SourcesResponse {
  sources: Source[];
  count: number;
}

export interface HealthResponse {
  status: string;
  brain_loaded: boolean;
  index_loaded?: boolean;
  source_count?: number;
  llm_provider?: string;
  llm_model?: string;
  embedding_provider?: string;
  embedding_model?: string;
  search_type?: string;
  top_k?: number;
  chat_storage?: string;
  persona?: string | null;
  index_metadata?: {
    chunk_count?: number;
    source_count?: number;
    sources?: string[];
    updated_at?: string;
  } | null;
}

export interface ChatSessionPayload {
  clientId: string;
  title: string;
  preview: string;
  messages: StoredMessage[];
}

export interface ChatSessionResponse {
  id: string;
  title: string;
  preview: string;
  created_at: string;
  updated_at: string;
  message_count: number;
  messages: StoredMessage[];
}

export interface ChatSessionsResponse {
  sessions: Array<{
    id: string;
    title: string;
    preview: string;
    created_at: string;
    updated_at: string;
    message_count: number;
  }>;
  count: number;
}

function toChatSessionSummary(session: ChatSessionsResponse["sessions"][number]): ChatSessionSummary {
  return {
    id: session.id,
    title: session.title,
    preview: session.preview,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    messageCount: session.message_count,
  };
}

export function toChatSessionSummaryFromDetail(session: ChatSessionResponse): ChatSessionSummary {
  return {
    id: session.id,
    title: session.title,
    preview: session.preview,
    createdAt: session.created_at,
    updatedAt: session.updated_at,
    messageCount: session.message_count,
  };
}

export async function sendMessage(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function uploadFile(
  file: File
): Promise<{ success: boolean; message: string; filename: string }> {
  const formData = new FormData();
  formData.append("file", file);

  const response = await fetch(`${API_BASE_URL}/v1/upload`, {
    method: "POST",
    body: formData,
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function getSources(): Promise<SourcesResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/sources`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function deleteSource(
  filename: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(
    `${API_BASE_URL}/v1/sources/${encodeURIComponent(filename)}`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function checkHealth(): Promise<HealthResponse> {
  const response = await fetch(`${API_BASE_URL}/health`);

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function listChatSessions(clientId: string): Promise<ChatSessionSummary[]> {
  const response = await fetch(
    `${API_BASE_URL}/v1/chats?client_id=${encodeURIComponent(clientId)}`
  );

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  const data: ChatSessionsResponse = await response.json();
  return data.sessions.map(toChatSessionSummary);
}

export async function getChatSession(
  chatId: string,
  clientId: string
): Promise<ChatSessionResponse> {
  const response = await fetch(
    `${API_BASE_URL}/v1/chats/${encodeURIComponent(chatId)}?client_id=${encodeURIComponent(clientId)}`
  );

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function createChatSession(
  payload: ChatSessionPayload
): Promise<ChatSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/chats`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      client_id: payload.clientId,
      title: payload.title,
      preview: payload.preview,
      messages: payload.messages,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function updateChatSession(
  chatId: string,
  payload: ChatSessionPayload
): Promise<ChatSessionResponse> {
  const response = await fetch(`${API_BASE_URL}/v1/chats/${encodeURIComponent(chatId)}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      client_id: payload.clientId,
      title: payload.title,
      preview: payload.preview,
      messages: payload.messages,
    }),
  });

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}

export async function deleteChatSession(
  chatId: string,
  clientId: string
): Promise<{ success: boolean; message: string }> {
  const response = await fetch(
    `${API_BASE_URL}/v1/chats/${encodeURIComponent(chatId)}?client_id=${encodeURIComponent(clientId)}`,
    {
      method: "DELETE",
    }
  );

  if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
  }

  return response.json();
}
