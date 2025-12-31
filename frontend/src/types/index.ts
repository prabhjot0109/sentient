export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
}

export interface Source {
  name: string;
  path: string;
  size: number;
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
