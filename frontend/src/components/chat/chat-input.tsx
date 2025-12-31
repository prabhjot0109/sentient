import { useState, useRef, KeyboardEvent } from "react";
import {
  Box,
  InputBase,
  IconButton,
  CircularProgress,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  ArrowUpward as SendIcon,
  KeyboardCommandKey as CommandIcon,
} from "@mui/icons-material";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
}

export function ChatInput({
  onSend,
  isLoading = false,
  disabled = false,
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleSubmit = () => {
    if (input.trim() && !isLoading && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = input.trim() && !isLoading && !disabled;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-end",
        gap: 2,
        position: "relative",
      }}
    >
      <InputBase
        multiline
        fullWidth
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Query your research brain—type anything..."
        disabled={isLoading || disabled}
        sx={{
          flex: 1,
          px: 1.5,
          py: 0.5, // Reduced from 0.8
          color: "text.primary",
          fontSize: "0.95rem",
          lineHeight: 1.5,
          "& .MuiInputBase-input": {
            "&::placeholder": {
              color: "text.secondary",
              opacity: 0.35, // Slightly more subtle
              fontStyle: "normal",
            },
          },
        }}
        inputProps={{
          ref: inputRef,
          style: { maxHeight: "200px" },
        }}
      />

      <Box sx={{ display: "flex", alignItems: "center", gap: 1.5, mb: 0.5 }}>
        <Box
          sx={{
            display: { xs: "none", md: "flex" },
            alignItems: "center",
            gap: 0.5,
            px: 1, // Reduced from 1.2
            py: 0.4, // Reduced from 0.6
            borderRadius: 1.5,
            border: "1px solid rgba(255, 255, 255, 0.06)",
            backgroundColor: "rgba(255, 255, 255, 0.03)",
            opacity: input.trim() ? 0.8 : 0.15,
            transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
          }}
        >
          <CommandIcon
            sx={{ fontSize: 10, color: "text.secondary", opacity: 0.6 }}
          />
          <Typography
            sx={{
              fontSize: 9, // Slightly smaller
              fontWeight: 700,
              color: "text.secondary",
              letterSpacing: 0.5,
              opacity: 0.6,
            }}
          >
            ENTER
          </Typography>
        </Box>

        <Tooltip title="Send inquiry">
          <IconButton
            onClick={handleSubmit}
            disabled={!canSend}
            sx={{
              width: 38, // Reduced from 42
              height: 38, // Reduced from 42
              borderRadius: 3, // More concise
              backgroundColor: canSend
                ? "rgba(59, 130, 246, 1)"
                : "rgba(255, 255, 255, 0.04)",
              color: canSend ? "white" : "rgba(255, 255, 255, 0.2)",
              transition: "all 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
              boxShadow: canSend
                ? "0 10px 20px -5px rgba(59, 130, 246, 0.3)"
                : "none",
              "&:hover": {
                backgroundColor: canSend
                  ? "rgba(59, 130, 246, 0.9)"
                  : "rgba(255, 255, 255, 0.08)",
                transform: canSend ? "translateY(-2px) scale(1.05)" : "none",
                color: canSend ? "white" : "rgba(255, 255, 255, 0.4)",
              },
              "&:active": { transform: "scale(0.95)" },
            }}
          >
            {isLoading ? (
              <CircularProgress size={20} color="inherit" />
            ) : (
              <SendIcon sx={{ fontSize: 18 }} />
            )}
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}
