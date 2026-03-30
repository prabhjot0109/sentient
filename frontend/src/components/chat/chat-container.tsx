import { useEffect, useRef } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  Container,
  Divider,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import {
  MenuOpen as MenuIcon,
} from "@mui/icons-material";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import type { Message } from "@/types";

interface ChatContainerProps {
  apiKey?: string;
  hasApiKey: boolean;
  isMobile: boolean;
  onOpenSettings: () => void;
  onToggleSidebar: () => void;
  messages: Message[];
  isLoading: boolean;
  isHistoryLoading: boolean;
  error: string | null;
  onSend: (message: string, apiKey?: string) => void;
  activeChatId: string | null;
  activeChatTitle: string;
}

export function ChatContainer({
  apiKey,
  hasApiKey,
  isMobile,
  onOpenSettings,
  onToggleSidebar,
  messages,
  isLoading,
  isHistoryLoading,
  error,
  onSend,
  activeChatId,
  activeChatTitle,
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = (message: string) => {
    onSend(message, apiKey);
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        flex: 1,
        minWidth: 0,
        minHeight: 0,
        height: "100%",
        overflow: "hidden",
        backgroundColor: "var(--surface-base)",
      }}
    >
      <Box
        sx={{
          minHeight: 56,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 2,
          px: { xs: 2, md: 2.5 },
          py: 1.5,
          borderBottom: "1px solid var(--stroke-subtle)",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, minWidth: 0 }}>
          {isMobile && (
            <IconButton
              onClick={onToggleSidebar}
              size="small"
              sx={{
                color: "text.secondary",
                "&:hover": { bgcolor: "rgba(255, 255, 255, 0.06)" },
              }}
            >
              <MenuIcon sx={{ fontSize: 18 }} />
            </IconButton>
          )}
          <Box sx={{ minWidth: 0 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              {activeChatTitle}
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              {activeChatId
                ? `${messages.length} messages`
                : "Start a new conversation"}
            </Typography>
          </Box>
        </Box>
      </Box>

      {!hasApiKey && (
        <Box sx={{ px: { xs: 2, md: 3 }, pt: 2 }}>
          <Alert
            severity="info"
            action={
              <Button color="inherit" size="small" onClick={onOpenSettings}>
                Add key
              </Button>
            }
          >
            Add your OpenRouter or OpenAI API key to use chat.
          </Alert>
        </Box>
      )}

      {error && (
        <Box sx={{ px: { xs: 2, md: 3 }, pt: 2 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}

      <Box
        ref={scrollRef}
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
        }}
      >
        {isHistoryLoading ? (
          <Container
            maxWidth="md"
            sx={{
              minHeight: "100%",
              display: "grid",
              placeItems: "center",
              py: 6,
            }}
          >
            <Box sx={{ display: "grid", justifyItems: "center", gap: 1.5 }}>
              <CircularProgress size={24} />
              <Typography variant="body2" sx={{ color: "text.secondary" }}>
                Loading chat history
              </Typography>
            </Box>
          </Container>
        ) : messages.length === 0 ? (
          <EmptyState
            onSuggestionClick={handleSend}
          />
        ) : (
          <Container maxWidth="md" sx={{ py: { xs: 3, md: 4 }, pb: 4 }}>
            <Stack spacing={3}>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isLoading && <TypingIndicator />}
            </Stack>
          </Container>
        )}
      </Box>

      <Divider />

      <Box
        sx={{
          px: { xs: 1.5, md: 2.5 },
          py: { xs: 1.5, md: 1.75 },
          bgcolor: "var(--surface-base)",
        }}
      >
        <Container maxWidth="md" disableGutters>
          <ChatInput
            onSend={handleSend}
            isLoading={isLoading}
            placeholder={
              hasApiKey ? "Message NPC" : "Add your API key, then ask a question"
            }
          />
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              alignItems: "center",
              mt: 1,
            }}
          >
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              Sentient can make mistakes. Verify important details.
            </Typography>
          </Box>
        </Container>
      </Box>
    </Box>
  );
}

function EmptyState({
  onSuggestionClick,
}: {
  onSuggestionClick: (text: string) => void;
}) {
  const suggestions = [
    "Summarize the key findings",
    "List the most important risks",
    "Compare the main themes",
    "Draft a short briefing",
  ];

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100%",
        py: { xs: 6, md: 8 },
        px: 4,
        textAlign: "center",
      }}
    >
      <Typography
        variant="h2"
        sx={{
          fontWeight: 800,
          color: "text.primary",
          fontSize: { xs: "2.5rem", md: "3rem" },
          letterSpacing: "-0.02em",
        }}
      >
        Sentient
      </Typography>
      <Typography
        variant="body1"
        sx={{
          color: "text.secondary",
          maxWidth: 500,
          mt: 1.5,
          mb: 5,
          fontSize: "1.1rem",
          fontWeight: 500,
        }}
      >
        An AI NPC that retrieves context from the lore of the game.
      </Typography>

      <Box sx={{ width: "100%", maxWidth: 800 }}>
        <Typography
          variant="overline"
          sx={{ display: "block", mb: 2.5, color: "text.secondary" }}
        >
          Try one of these
        </Typography>
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: 1.5,
          }}
        >
          {suggestions.map((text) => (
            <Button
              key={text}
              onClick={() => onSuggestionClick(text)}
              variant="outlined"
              sx={{
                py: 1.1,
                px: 2,
                borderColor: "var(--stroke-subtle)",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                color: "text.primary",
                borderRadius: 2,
                fontWeight: 600,
                fontSize: "0.85rem",
                "&:hover": {
                  borderColor: "rgba(255, 255, 255, 0.18)",
                  backgroundColor: "rgba(255, 255, 255, 0.04)",
                },
              }}
            >
              {text}
            </Button>
          ))}
        </Box>
      </Box>
    </Box>
  );
}

function TypingIndicator() {
  return (
    <Box sx={{ display: "inline-flex", alignItems: "center", gap: 0.75, px: 0.5, py: 0.5 }}>
      <Box sx={{ display: "flex", gap: 0.75 }}>
        {[0, 1, 2].map((i) => (
          <Box
            key={i}
            sx={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: "rgba(255, 255, 255, 0.36)",
              animation: "pulse 1.2s ease-in-out infinite",
              animationDelay: `${i * 0.14}s`,
            }}
          />
        ))}
      </Box>
    </Box>
  );
}
