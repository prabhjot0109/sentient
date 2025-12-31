import { useEffect, useRef } from "react";
import {
  Box,
  Typography,
  IconButton,
  Container,
  Paper,
  Stack,
  Button,
  Avatar,
} from "@mui/material";
import {
  HistoryEdu as HistoryIcon,
  MenuOpen as MenuIcon,
  AutoAwesome as SparklesIcon,
} from "@mui/icons-material";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ChatMessage } from "./chat-message";
import { ChatInput } from "./chat-input";
import { useChat } from "@/hooks/use-chat";

interface ChatContainerProps {
  apiKey?: string;
  sidebarOpen: boolean;
  onToggleSidebar: () => void;
}

export function ChatContainer({
  apiKey,
  sidebarOpen,
  onToggleSidebar,
}: ChatContainerProps) {
  const { messages, isLoading, sendMessage } = useChat();
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = (message: string) => {
    sendMessage(message, apiKey);
  };

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        position: "relative",
      }}
    >
      {/* App Bar / Header */}
      <Box
        sx={{
          height: 64,
          display: "flex",
          alignItems: "center",
          px: 3,
          borderBottom: "1px solid rgba(255, 255, 255, 0.05)",
          zIndex: 20,
          backgroundColor: "rgba(9, 9, 11, 0.5)",
          backdropFilter: "blur(20px)",
        }}
      >
        {!sidebarOpen && (
          <IconButton
            onClick={onToggleSidebar}
            size="small"
            sx={{ mr: 2, color: "text.secondary" }}
          >
            <MenuIcon />
          </IconButton>
        )}
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5 }}>
          <HistoryIcon sx={{ color: "primary.main", fontSize: 20 }} />
          <Typography
            variant="subtitle2"
            sx={{ fontWeight: 700, opacity: 0.8 }}
          >
            Intelligent Notebook
          </Typography>
        </Box>
      </Box>

      {/* Messages Viewport */}
      <Box sx={{ flex: 1, overflow: "hidden" }}>
        <ScrollArea className="h-full" ref={scrollRef}>
          {messages.length === 0 ? (
            <EmptyState onSuggestionClick={handleSend} />
          ) : (
            <Container maxWidth="md" sx={{ py: 6, pb: 24 }}>
              <Stack spacing={4}>
                {messages.map((message) => (
                  <ChatMessage key={message.id} message={message} />
                ))}
                {isLoading && <TypingIndicator />}
              </Stack>
            </Container>
          )}
        </ScrollArea>
      </Box>

      {/* Input Section - Floating style */}
      <Box
        sx={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          pb: 4,
          pt: 8,
          background: "linear-gradient(to top, #09090b 40%, transparent)",
          zIndex: 30,
        }}
      >
        <Container maxWidth="md">
          <Paper
            elevation={24}
            sx={{
              p: 1.5,
              borderRadius: 6,
              backgroundColor: "background.paper",
              border: "1px solid rgba(255, 255, 255, 0.08)",
              boxShadow: "0 25px 50px -12px rgba(0, 0, 0, 0.5)",
            }}
          >
            <ChatInput onSend={handleSend} isLoading={isLoading} />
          </Paper>
          <Typography
            variant="caption"
            sx={{
              display: "block",
              textAlign: "center",
              mt: 2,
              opacity: 0.3,
              fontWeight: 700,
              letterSpacing: 1,
            }}
          >
            SENTIENT CORE • NEURAL RAG ENGINE
          </Typography>
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
    "Summarize these findings",
    "Identify critical themes",
    "List technical specifications",
    "Draft a synthesis report",
  ];

  return (
    <Box
      sx={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "calc(100vh - 200px)",
        px: 4,
        textAlign: "center",
      }}
    >
      <Paper
        sx={{
          width: 80,
          height: 80,
          borderRadius: 5,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "linear-gradient(135deg, #3b82f6 0%, #2dd4bf 100%)",
          mb: 4,
          boxShadow: "0 20px 40px rgba(59, 130, 246, 0.3)",
        }}
      >
        <SparklesIcon sx={{ fontSize: 40, color: "white" }} />
      </Paper>

      <Typography
        variant="h3"
        gutterBottom
        sx={{ fontWeight: 800, letterSpacing: -1, color: "white" }}
      >
        A more sentient{" "}
        <Box component="span" sx={{ color: "primary.main" }}>
          notebook
        </Box>
        .
      </Typography>
      <Typography
        variant="body1"
        sx={{
          color: "text.secondary",
          maxWidth: 500,
          mb: 6,
          fontSize: "1.1rem",
        }}
      >
        Synthesizing knowledge from your documents to provide deep, actionable
        insights. Ask me anything about your uploaded sources.
      </Typography>

      <Stack
        direction={{ xs: "column", sm: "row" }}
        spacing={2}
        sx={{ width: "100%", maxWidth: 700 }}
      >
        {suggestions.map((text) => (
          <Button
            key={text}
            fullWidth
            onClick={() => onSuggestionClick(text)}
            variant="outlined"
            sx={{
              py: 2,
              borderColor: "rgba(255, 255, 255, 0.05)",
              backgroundColor: "rgba(255, 255, 255, 0.02)",
              color: "text.primary",
              borderRadius: 4,
              "&:hover": {
                borderColor: "primary.main",
                backgroundColor: "rgba(59, 130, 246, 0.1)",
              },
            }}
          >
            {text}
          </Button>
        ))}
      </Stack>
    </Box>
  );
}

function TypingIndicator() {
  return (
    <Box sx={{ display: "flex", gap: 2, alignItems: "flex-start" }}>
      <Avatar
        sx={{
          width: 32,
          height: 32,
          bgcolor: "background.paper",
          border: "1px solid rgba(255, 255, 255, 0.1)",
        }}
      >
        <SparklesIcon sx={{ fontSize: 16, color: "primary.main" }} />
      </Avatar>
      <Box sx={{ pt: 1, display: "flex", gap: 0.5 }}>
        {[0, 1, 2].map((i) => (
          <Box
            key={i}
            sx={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              backgroundColor: "rgba(255, 255, 255, 0.3)",
              animation: "pulse 1.4s ease-in-out infinite",
              animationDelay: `${i * 0.2}s`,
            }}
          />
        ))}
      </Box>
    </Box>
  );
}
