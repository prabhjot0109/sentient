export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export interface StoredMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
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

export interface ChatSession extends ChatSessionSummary {
  messages: Message[];
}

export interface ChatState {
  messages: Message[];
  isLoading: boolean;
  error: string | null;
}

export interface SourcesState {
  sources: Source[];
  isLoading: boolean;
  error: string | null;
}
