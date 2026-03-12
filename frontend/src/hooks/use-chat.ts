import { useCallback, useEffect, useState } from "react";
import {
  createChatSession,
  deleteChatSession,
  getChatSession,
  listChatSessions,
  sendMessage,
  toChatSessionSummaryFromDetail,
  updateChatSession,
} from "@/lib/api";
import type { ChatSessionSummary, Message, StoredMessage } from "@/types";

const CLIENT_ID_STORAGE_KEY = "sentient_client_id";

function getClientId() {
  if (typeof window === "undefined") {
    return "server";
  }

  const existingClientId = localStorage.getItem(CLIENT_ID_STORAGE_KEY);
  if (existingClientId) {
    return existingClientId;
  }

  const nextClientId = crypto.randomUUID();
  localStorage.setItem(CLIENT_ID_STORAGE_KEY, nextClientId);
  return nextClientId;
}

function serializeMessages(messages: Message[]): StoredMessage[] {
  return messages.map((message) => ({
    id: message.id,
    role: message.role,
    content: message.content,
    timestamp: message.timestamp.toISOString(),
  }));
}

function deserializeMessages(messages: StoredMessage[]): Message[] {
  return messages.map((message) => ({
    ...message,
    timestamp: new Date(message.timestamp),
  }));
}

function deriveChatTitle(messages: Message[]) {
  const firstUserMessage = messages.find((message) => message.role === "user");
  if (!firstUserMessage) {
    return "New chat";
  }

  return firstUserMessage.content.slice(0, 48).trim() || "New chat";
}

function deriveChatPreview(messages: Message[]) {
  const lastMessage = [...messages].reverse().find((message) => message.content.trim());
  if (!lastMessage) {
    return "";
  }

  return lastMessage.content.slice(0, 120).trim();
}

function sortSessions(sessions: ChatSessionSummary[]) {
  return [...sessions].sort(
    (left, right) =>
      new Date(right.updatedAt).getTime() - new Date(left.updatedAt).getTime()
  );
}

export function useChat() {
  const [clientId] = useState(() => getClientId());
  const [chats, setChats] = useState<ChatSessionSummary[]>([]);
  const [activeChatId, setActiveChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isHistoryLoading, setIsHistoryLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const upsertSessionSummary = useCallback((summary: ChatSessionSummary) => {
    setChats((prev) =>
      sortSessions([
        summary,
        ...prev.filter((session) => session.id !== summary.id),
      ])
    );
  }, []);

  const loadChat = useCallback(
    async (chatId: string) => {
      setIsHistoryLoading(true);
      setError(null);

      try {
        const session = await getChatSession(chatId, clientId);
        setActiveChatId(session.id);
        setMessages(deserializeMessages(session.messages));
        upsertSessionSummary(toChatSessionSummaryFromDetail(session));
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to load chat";
        setError(errorMessage);
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [clientId, upsertSessionSummary]
  );

  const refreshChats = useCallback(
    async (chatIdToOpen?: string | null) => {
      setIsHistoryLoading(true);
      setError(null);

      try {
        const sessions = await listChatSessions(clientId);
        const sortedSessions = sortSessions(sessions);
        setChats(sortedSessions);

        const targetChatId = chatIdToOpen ?? activeChatId ?? sortedSessions[0]?.id ?? null;

        if (targetChatId) {
          const session = await getChatSession(targetChatId, clientId);
          setActiveChatId(session.id);
          setMessages(deserializeMessages(session.messages));
          upsertSessionSummary(toChatSessionSummaryFromDetail(session));
        } else {
          setActiveChatId(null);
          setMessages([]);
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to load chat history";
        setError(errorMessage);
      } finally {
        setIsHistoryLoading(false);
      }
    },
    [activeChatId, clientId, upsertSessionSummary]
  );

  useEffect(() => {
    refreshChats(null);
  }, [refreshChats]);

  const persistMessages = useCallback(
    async (nextMessages: Message[], chatId: string | null) => {
      const payload = {
        clientId,
        title: deriveChatTitle(nextMessages),
        preview: deriveChatPreview(nextMessages),
        messages: serializeMessages(nextMessages),
      };

      if (chatId) {
        const session = await updateChatSession(chatId, payload);
        upsertSessionSummary(toChatSessionSummaryFromDetail(session));
        return session.id;
      }

      const session = await createChatSession(payload);
      setActiveChatId(session.id);
      upsertSessionSummary(toChatSessionSummaryFromDetail(session));
      return session.id;
    },
    [clientId, upsertSessionSummary]
  );

  const sendUserMessage = useCallback(
    async (content: string, apiKey?: string) => {
      if (!content.trim()) return;

      const userMessage: Message = {
        id: crypto.randomUUID(),
        role: "user",
        content: content.trim(),
        timestamp: new Date(),
      };

      const userMessages = [...messages, userMessage];

      setMessages(userMessages);
      setIsLoading(true);
      setError(null);

      try {
        const response = await sendMessage(content, apiKey);

        let nextMessages = userMessages;

        if (response.success) {
          const assistantMessage: Message = {
            id: crypto.randomUUID(),
            role: "assistant",
            content: response.response,
            timestamp: new Date(),
          };
          nextMessages = [...userMessages, assistantMessage];
          setMessages(nextMessages);
        } else {
          setError(response.response);
        }

        const savedChatId = await persistMessages(nextMessages, activeChatId);
        if (!activeChatId) {
          setActiveChatId(savedChatId);
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to send message";
        setError(errorMessage);

        const errorAssistantMessage: Message = {
          id: crypto.randomUUID(),
          role: "assistant",
          content: `Sorry, I encountered an error: ${errorMessage}. Please make sure the backend server is running.`,
          timestamp: new Date(),
        };

        const nextMessages = [...userMessages, errorAssistantMessage];
        setMessages(nextMessages);

        try {
          const savedChatId = await persistMessages(nextMessages, activeChatId);
          if (!activeChatId) {
            setActiveChatId(savedChatId);
          }
        } catch (persistError) {
          const persistenceError =
            persistError instanceof Error
              ? persistError.message
              : "Failed to persist chat";
          setError(`${errorMessage}. ${persistenceError}`);
        }
      } finally {
        setIsLoading(false);
      }
    },
    [activeChatId, messages, persistMessages]
  );

  const clearMessages = useCallback(() => {
    setActiveChatId(null);
    setMessages([]);
    setError(null);
  }, []);

  const removeChat = useCallback(
    async (chatId: string) => {
      const isCurrentChat = chatId === activeChatId;
      setError(null);

      try {
        await deleteChatSession(chatId, clientId);
        const remainingChats = chats.filter((chat) => chat.id !== chatId);
        setChats(remainingChats);

        if (isCurrentChat) {
          const nextChatId = remainingChats[0]?.id ?? null;
          if (nextChatId) {
            await loadChat(nextChatId);
          } else {
            clearMessages();
          }
        }
      } catch (err) {
        const errorMessage =
          err instanceof Error ? err.message : "Failed to delete chat";
        setError(errorMessage);
      }
    },
    [activeChatId, chats, clearMessages, clientId, loadChat]
  );

  return {
    chats,
    activeChatId,
    messages,
    isLoading,
    isHistoryLoading,
    error,
    sendMessage: sendUserMessage,
    clearMessages,
    loadChat,
    removeChat,
  };
}
