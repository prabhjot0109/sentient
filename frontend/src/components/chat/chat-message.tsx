import { useState } from "react";
import { 
  Box, 
  Typography, 
  Avatar, 
  IconButton, 
  Tooltip,
} from "@mui/material";
import { 
  ContentCopy as CopyIcon, 
  Check as CheckIcon,
  Person as UserIcon,
  AutoAwesome as SparklesIcon
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
    <Box sx={{ 
      display: 'flex', 
      gap: 3, 
      flexDirection: isUser ? 'row-reverse' : 'row',
      alignItems: 'flex-start'
    }}>
      {/* Avatar Section */}
      <Avatar
        sx={{
          width: 36,
          height: 36,
          borderRadius: 2,
          bgcolor: isUser ? 'rgba(59, 130, 246, 0.1)' : 'rgba(255, 255, 255, 0.03)',
          color: isUser ? 'primary.main' : 'primary.light',
          border: '1px solid rgba(255, 255, 255, 0.05)',
          boxShadow: isUser ? 'none' : '0 4px 12px rgba(0,0,0,0.5)',
          flexShrink: 0
        }}
      >
        {isUser ? <UserIcon fontSize="small" /> : <SparklesIcon fontSize="small" />}
      </Avatar>

      {/* Content Section */}
      <Box sx={{ 
        maxWidth: '85%', 
        display: 'flex', 
        flexDirection: 'column',
        alignItems: isUser ? 'flex-end' : 'flex-start'
      }}>
        <Typography 
          variant="caption" 
          sx={{ 
            mb: 1, 
            opacity: 0.3, 
            fontWeight: 800, 
            letterSpacing: 1,
            textTransform: 'uppercase'
          }}
        >
          {isUser ? 'Session Operator' : 'Cognitive Core'}
        </Typography>

        <Box sx={{ position: 'relative', '&:hover .message-ops': { opacity: 1 } }}>
          <Box sx={{
            px: 3,
            py: 2,
            borderRadius: 4,
            backgroundColor: isUser ? 'primary.main' : 'rgba(255, 255, 255, 0.02)',
            color: isUser ? 'white' : 'text.primary',
            border: isUser ? 'none' : '1px solid rgba(255, 255, 255, 0.04)',
            boxShadow: isUser ? '0 10px 20px rgba(59, 130, 246, 0.15)' : 'none',
            fontSize: '0.95rem',
            lineHeight: 1.7,
            whiteSpace: 'pre-wrap',
            fontFamily: 'Inter, sans-serif'
          }}>
            {message.content}
          </Box>

          {!isUser && (
            <Box 
              className="message-ops"
              sx={{ 
                position: 'absolute', 
                right: -48, 
                top: 0, 
                opacity: 0, 
                transition: 'opacity 0.2s',
                display: 'flex',
                flexDirection: 'column',
                gap: 1
              }}
            >
              <Tooltip title="Copy to clipboard" placement="right">
                <IconButton 
                  size="small" 
                  onClick={handleCopy}
                  sx={{ 
                    bgcolor: 'background.paper',
                    border: '1px solid rgba(255, 255, 255, 0.05)',
                    p: 1,
                    '&:hover': { bgcolor: 'rgba(255, 255, 255, 0.05)' }
                  }}
                >
                  {copied ? <CheckIcon fontSize="inherit" color="success" /> : <CopyIcon fontSize="inherit" />}
                </IconButton>
              </Tooltip>
            </Box>
          )}
        </Box>
      </Box>
    </Box>
  );
}
