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
  onToggleSidebar: () => void;
}

export function ChatContainer({ apiKey, onToggleSidebar }: ChatContainerProps) {
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
        background:
          "radial-gradient(circle at 50% 0%, rgba(59, 130, 246, 0.05) 0%, transparent 50%)",
      }}
    >
      {/* App Bar / Header */}
      <Box
        sx={{
          height: 72,
          display: "flex",
          alignItems: "center",
          px: 3,
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
          zIndex: 20,
          backgroundColor: "rgba(9, 9, 11, 0.7)",
          backdropFilter: "blur(20px)",
        }}
      >
        <IconButton
          onClick={onToggleSidebar}
          size="small"
          sx={{
            mr: 2,
            color: "text.secondary",
            bgcolor: "rgba(255, 255, 255, 0.03)",
            "&:hover": { bgcolor: "rgba(255, 255, 255, 0.08)" },
          }}
        >
          <MenuIcon sx={{ fontSize: 20 }} />
        </IconButton>

        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Box
            sx={{
              p: 0.8,
              borderRadius: 2.5,
              bgcolor: "rgba(59, 130, 246, 0.1)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            <HistoryIcon sx={{ color: "primary.main", fontSize: 18 }} />
          </Box>
          <Box>
            <Typography
              variant="subtitle2"
              sx={{
                fontWeight: 850,
                letterSpacing: -0.2,
                fontSize: "0.9rem",
                color: "white",
              }}
            >
              Intelligent Notebook
            </Typography>
            <Typography
              variant="caption"
              sx={{
                color: "text.secondary",
                fontWeight: 600,
                opacity: 0.5,
                display: "block",
                mt: -0.5,
              }}
            >
              Powered by Sentient Neural Core
            </Typography>
          </Box>
        </Box>
      </Box>

      {/* Messages Viewport */}
      <Box sx={{ flex: 1, overflow: "hidden", position: "relative" }}>
        <ScrollArea className="h-full" ref={scrollRef}>
          {messages.length === 0 ? (
            <EmptyState onSuggestionClick={handleSend} />
          ) : (
            <Container maxWidth="md" sx={{ py: 8, pb: 32 }}>
              <Stack spacing={5}>
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
          pt: 10,
          background: "linear-gradient(to top, #09090b 80%, transparent)",
          zIndex: 30,
          pointerEvents: "none",
        }}
      >
        <Container maxWidth="md" sx={{ pointerEvents: "auto" }}>
          <Paper
            elevation={0}
            sx={{
              p: 1.5,
              borderRadius: 5,
              backgroundColor: "rgba(18, 18, 21, 0.8)",
              backdropFilter: "blur(20px)",
              border: "1px solid rgba(255, 255, 255, 0.1)",
              boxShadow: "0 32px 64px -16px rgba(0, 0, 0, 0.8)",
            }}
          >
            <ChatInput onSend={handleSend} isLoading={isLoading} />
          </Paper>
          <Box
            sx={{
              display: "flex",
              justifyContent: "center",
              gap: 4,
              mt: 3,
              opacity: 0.4,
            }}
          >
            <Typography
              variant="caption"
              sx={{
                fontWeight: 800,
                letterSpacing: 1.5,
                fontSize: "0.6rem",
                color: "text.secondary",
              }}
            >
              NEURAL RAG • CORE V1.0
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
        minHeight: "100%",
        py: 4,
        pb: 20, // Reduced bottom padding to prevent push-up
        px: 4,
        textAlign: "center",
      }}
    >
      <Box sx={{ position: "relative", mb: 6 }}>
        <Box
          sx={{
            width: 100,
            height: 100,
            borderRadius: 6,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            background: "linear-gradient(135deg, #3b82f6 0%, #2dd4bf 100%)",
            boxShadow: "0 24px 48px rgba(59, 130, 246, 0.4)",
          }}
        >
          <SparklesIcon sx={{ fontSize: 48, color: "white" }} />
        </Box>
        <Box
          sx={{
            position: "absolute",
            inset: -20,
            border: "1px solid rgba(59, 130, 246, 0.1)",
            borderRadius: 8,
            zIndex: -1,
            animation: "pulse 3s infinite",
          }}
        />
      </Box>

      <Typography
        variant="h2"
        gutterBottom
        sx={{
          fontWeight: 850,
          letterSpacing: -1.5,
          color: "white",
          fontSize: { xs: "2rem", md: "3rem" },
        }}
      >
        Think deeper with your{" "}
        <Box
          component="span"
          sx={{
            background: "linear-gradient(135deg, #3b82f6 0%, #2dd4bf 100%)",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
          }}
        >
          knowledge
        </Box>
        .
      </Typography>
      <Typography
        variant="body1"
        sx={{
          color: "text.secondary",
          maxWidth: 600,
          mb: 8,
          fontSize: "1.2rem",
          fontWeight: 500,
          lineHeight: 1.6,
          opacity: 0.7,
        }}
      >
        SENTIENT synthesizes complex documents into conversational intelligence.
        Upload your sources and start exploring the core insights today.
      </Typography>

      <Box sx={{ width: "100%", maxWidth: 800 }}>
        <Typography
          variant="overline"
          sx={{
            display: "block",
            mb: 3,
            fontWeight: 900,
            opacity: 0.4,
            letterSpacing: 2,
          }}
        >
          Suggested Inquiries
        </Typography>
        <Box
          sx={{
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "center",
            gap: 2,
          }}
        >
          {suggestions.map((text) => (
            <Button
              key={text}
              onClick={() => onSuggestionClick(text)}
              variant="outlined"
              sx={{
                py: 1.5,
                px: 3,
                borderColor: "rgba(255, 255, 255, 0.06)",
                backgroundColor: "rgba(255, 255, 255, 0.03)",
                color: "text.primary",
                borderRadius: 3,
                fontWeight: 700,
                fontSize: "0.85rem",
                "&:hover": {
                  borderColor: "primary.main",
                  backgroundColor: "rgba(59, 130, 246, 0.08)",
                  transform: "translateY(-2px)",
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
