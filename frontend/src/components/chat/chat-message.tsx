import { useState } from "react";
import { Box, IconButton, Tooltip, Typography } from "@mui/material";
import {
  Check as CheckIcon,
  ContentCopy as CopyIcon,
} from "@mui/icons-material";
import { formatDate } from "@/lib/utils";
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
        justifyContent: isUser ? "flex-end" : "flex-start",
        width: "100%",
      }}
    >
      <Box
        sx={{
          width: "100%",
          maxWidth: isUser ? 720 : "100%",
          borderRadius: isUser ? 3 : 0,
          border: isUser ? "1px solid var(--stroke-subtle)" : "none",
          backgroundColor: isUser ? "#303030" : "transparent",
          px: { xs: 1.5, md: isUser ? 2 : 0 },
          py: isUser ? 1.25 : 0,
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 1.5,
            mb: isUser ? 0.75 : 0.5,
          }}
        >
          <Typography variant="caption" sx={{ color: "text.secondary" }}>
            {isUser
              ? `You • ${formatDate(message.timestamp)}`
              : `Sentient • ${formatDate(message.timestamp)}`}
          </Typography>

          {!isUser && (
            <Tooltip title={copied ? "Copied" : "Copy response"}>
              <IconButton
                size="small"
                onClick={handleCopy}
                sx={{
                  color: copied ? "success.main" : "text.secondary",
                  p: 0.5,
                  "&:hover": { color: "text.primary" },
                }}
              >
                {copied ? (
                  <CheckIcon sx={{ fontSize: 15 }} />
                ) : (
                  <CopyIcon sx={{ fontSize: 15 }} />
                )}
              </IconButton>
            </Tooltip>
          )}
        </Box>

        <Typography
          component="div"
          sx={{
            color: "text.primary",
            fontSize: "0.98rem",
            lineHeight: 1.7,
            whiteSpace: "pre-wrap",
            fontWeight: 400,
          }}
        >
          {message.content}
        </Typography>
      </Box>
    </Box>
  );
}
