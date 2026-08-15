import { useEffect, useRef } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  Stack,
  Typography,
} from "@mui/material";
import { MenuOpen as MenuIcon } from "@mui/icons-material";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import type { Message } from "@/types";

// ChatGPT's reading column is ~768px; everything centers to this width.
const CONTENT_MAX = 768;

interface ChatContainerProps {
  isMobile: boolean;
  onToggleSidebar: () => void;
  messages: Message[];
  isLoading: boolean;
  isHistoryLoading: boolean;
  error: string | null;
  onSend: (message: string) => void;
  activeChatTitle: string;
}

export function ChatContainer({
  isMobile,
  onToggleSidebar,
  messages,
  isLoading,
  isHistoryLoading,
  error,
  onSend,
  activeChatTitle,
}: ChatContainerProps) {
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, isLoading]);

  const handleSend = (message: string) => {
    onSend(message);
  };

  const isEmpty = messages.length === 0 && !isHistoryLoading;

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
      {/* Minimal top bar — a menu toggle (shown when sidebar is closed or on mobile) and a title. */}
      <Box
        sx={{
          minHeight: 56,
          display: "flex",
          alignItems: "center",
          gap: 1.5,
          px: 2,
          borderBottom: "1px solid var(--stroke-subtle)",
          backgroundColor: "rgba(13, 13, 13, 0.6)",
          backdropFilter: "blur(8px)",
          position: "sticky",
          top: 0,
          zIndex: 10,
        }}
      >
        {isMobile && (
          <IconButton
            onClick={onToggleSidebar}
            size="small"
            aria-label="Toggle sidebar"
            sx={{
              color: "text.secondary",
              borderRadius: "8px",
              "&:hover": { color: "#ffffff", bgcolor: "rgba(255, 255, 255, 0.06)" },
            }}
          >
            <MenuIcon sx={{ fontSize: 20 }} />
          </IconButton>
        )}
        <Typography
          variant="body2"
          noWrap
          sx={{ color: "#ffffff", fontWeight: 600, fontSize: "0.9rem" }}
        >
          {activeChatTitle}
        </Typography>
      </Box>

      {error && (
        <Box sx={{ width: "100%", maxWidth: CONTENT_MAX, mx: "auto", px: 2, pt: 1 }}>
          <Alert severity="error">{error}</Alert>
        </Box>
      )}

      <Box ref={scrollRef} sx={{ flex: 1, minHeight: 0, overflowY: "auto" }}>
        {isHistoryLoading ? (
          <Box
            sx={{
              minHeight: "100%",
              display: "grid",
              placeItems: "center",
              gap: 1.5,
            }}
          >
            <CircularProgress size={22} color="inherit" />
          </Box>
        ) : isEmpty ? (
          <EmptyState onSuggestionClick={handleSend} />
        ) : (
          <Box
            sx={{
              width: "100%",
              maxWidth: CONTENT_MAX,
              mx: "auto",
              px: { xs: 2, md: 3 },
              py: { xs: 3, md: 4 },
            }}
          >
            <Stack spacing={3.5}>
              {messages.map((message) => (
                <ChatMessage key={message.id} message={message} />
              ))}
              {isLoading && <TypingIndicator />}
            </Stack>
          </Box>
        )}
      </Box>

      {/* Composer — pinned, centered to the reading column. */}
      <Box sx={{ px: { xs: 1.5, md: 3 }, pb: { xs: 1.5, md: 2 }, pt: 1 }}>
        <Box sx={{ width: "100%", maxWidth: CONTENT_MAX, mx: "auto" }}>
          <ChatInput
            onSend={handleSend}
            isLoading={isLoading}
            placeholder="Message Sentient"
          />
          <Typography
            variant="caption"
            sx={{
              display: "block",
              textAlign: "center",
              mt: 1,
              color: "text.secondary",
              fontSize: "0.72rem",
            }}
          >
            Sentient can make mistakes. Verify important details.
          </Typography>
        </Box>
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
    "Who are you?",
    "Tell me about this world",
    "What happened here?",
    "What should I know?",
  ];

  return (
    <Box
      sx={{
        minHeight: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        px: 3,
        py: 6,
        textAlign: "center",
      }}
    >
      <Typography
        sx={{
          fontWeight: 700,
          color: "#ffffff",
          fontSize: { xs: "1.7rem", md: "2rem" },
          letterSpacing: "-0.02em",
        }}
      >
        Ask your companion anything.
      </Typography>

      <Typography
        sx={{
          mt: 1,
          color: "text.secondary",
          fontSize: "0.95rem",
          maxWidth: 460,
          lineHeight: 1.5,
        }}
      >
        Answers are grounded in your uploaded lore, and fall back to general
        knowledge when it doesn't cover something.
      </Typography>

      <Box
        sx={{
          mt: 4,
          display: "flex",
          flexWrap: "wrap",
          justifyContent: "center",
          gap: 1.25,
          maxWidth: 560,
        }}
      >
        {suggestions.map((text) => (
          <Button
            key={text}
            onClick={() => onSuggestionClick(text)}
            sx={{
              px: 2.5,
              py: 1,
              borderRadius: "10px",
              border: "1px solid var(--stroke-subtle)",
              color: "text.secondary",
              fontWeight: 500,
              fontSize: "0.85rem",
              textTransform: "none",
              backgroundColor: "rgba(255, 255, 255, 0.02)",
              "&:hover": {
                color: "#ffffff",
                borderColor: "rgba(255, 255, 255, 0.3)",
                backgroundColor: "rgba(255, 255, 255, 0.06)",
              },
            }}
          >
            {text}
          </Button>
        ))}
      </Box>
    </Box>
  );
}

function TypingIndicator() {
  return (
    <Box sx={{ display: "flex", gap: 0.75, py: 1.5, pl: 0.5 }}>
      {[0, 1, 2].map((i) => (
        <Box
          key={i}
          sx={{
            width: 6,
            height: 6,
            borderRadius: "50%",
            backgroundColor: "rgba(255, 255, 255, 0.6)",
            animation: "pulse 1.2s ease-in-out infinite",
            animationDelay: `${i * 0.14}s`,
          }}
        />
      ))}
    </Box>
  );
}
