import { useState } from "react";
import { Box, Typography, Avatar, IconButton, Tooltip } from "@mui/material";
import {
  ContentCopy as CopyIcon,
  Check as CheckIcon,
  Person as UserIcon,
  AutoAwesome as SparklesIcon,
} from "@mui/icons-material";
import type { Message } from "@/types";

interface ChatMessageProps {
  message: Message;
}

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <Box
      sx={{
        display: "flex",
        gap: 3,
        flexDirection: "row",
        alignItems: "flex-start",
      }}
    >
      {/* Avatar Section */}
      <Avatar
        sx={{
          width: 36,
          height: 36,
          borderRadius: 1.5,
          bgcolor: isUser ? "#27272a" : "transparent",
          color: isUser ? "primary.main" : "primary.main",
          border: "1px solid rgba(255, 255, 255, 0.08)",
          boxShadow: isUser ? "none" : "none",
          flexShrink: 0,
          background: isUser
            ? "none"
            : "linear-gradient(135deg, rgba(59, 130, 246, 0.1) 0%, rgba(45, 212, 191, 0.1) 100%)",
        }}
      >
        {isUser ? (
          <UserIcon sx={{ fontSize: 18 }} />
        ) : (
          <SparklesIcon sx={{ fontSize: 18 }} />
        )}
      </Avatar>

      {/* Content Section */}
      <Box
        sx={{
          flex: 1,
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 0.5 }}>
          <Typography
            variant="caption"
            sx={{
              opacity: 0.4,
              fontWeight: 800,
              letterSpacing: 1,
              textTransform: "uppercase",
              fontSize: "0.65rem",
            }}
          >
            {isUser ? "Operator" : "AI Assistant"}
          </Typography>
          {!isUser && (
            <Box
              sx={{
                width: 4,
                height: 4,
                borderRadius: "50%",
                bgcolor: "primary.main",
                opacity: 0.5,
              }}
            />
          )}
        </Box>

        <Box
          sx={{
            position: "relative",
            width: "100%",
            "&:hover .message-ops": { opacity: 1 },
          }}
        >
          <Box
            sx={{
              color: "text.primary",
              fontSize: "1rem",
              lineHeight: 1.7,
              whiteSpace: "pre-wrap",
              fontFamily: "Inter, sans-serif",
              fontWeight: 450,
              py: 0.5,
            }}
          >
            {message.content}
          </Box>

          {!isUser && (
            <Box
              className="message-ops"
              sx={{
                position: "absolute",
                right: 0,
                bottom: -28,
                opacity: 0,
                transition: "opacity 0.2s",
                display: "flex",
                gap: 1,
              }}
            >
              <Tooltip title="Copy response">
                <IconButton
                  size="small"
                  onClick={handleCopy}
                  sx={{
                    color: "text.secondary",
                    p: 0.5,
                    "&:hover": { color: "primary.main" },
                  }}
                >
                  {copied ? (
                    <CheckIcon sx={{ fontSize: 14 }} color="success" />
                  ) : (
                    <CopyIcon sx={{ fontSize: 14 }} />
                  )}
                </IconButton>
              </Tooltip>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
}
