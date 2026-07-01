import { useRef, useState, type KeyboardEvent } from "react";
import { Box, CircularProgress, IconButton, InputBase } from "@mui/material";
import { ArrowUpward as SendIcon } from "@mui/icons-material";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  isLoading = false,
  disabled = false,
  placeholder = "Message NPC",
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | HTMLInputElement>(null);

  const handleSubmit = () => {
    if (input.trim() && !isLoading && !disabled) {
      onSend(input.trim());
      setInput("");
    }
  };

  const handleKeyDown = (
    e: KeyboardEvent<HTMLTextAreaElement | HTMLInputElement>
  ) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const canSend = Boolean(input.trim()) && !isLoading && !disabled;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-end",
        gap: 1,
        borderRadius: "28px",
        pl: 2.5,
        pr: 1,
        py: 0.75,
        border: "1px solid var(--stroke-subtle)",
        backgroundColor: "#303030",
        boxShadow: "0 2px 12px rgba(0, 0, 0, 0.25)",
        transition: "border-color 160ms ease, background-color 160ms ease",
        "&:focus-within": {
          borderColor: "rgba(255, 255, 255, 0.24)",
          backgroundColor: "#353535",
        },
      }}
    >
      <InputBase
        multiline
        fullWidth
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        disabled={isLoading || disabled}
        sx={{
          flex: 1,
          py: 1,
          color: "text.primary",
          fontSize: "1rem",
          lineHeight: 1.6,
          "& .MuiInputBase-input": {
            "&::placeholder": {
              color: "text.secondary",
              opacity: 0.8,
            },
          },
        }}
        inputProps={{
          ref: inputRef,
          style: { maxHeight: "200px" },
        }}
      />

      <IconButton
        onClick={handleSubmit}
        disabled={!canSend}
        aria-label="Send message"
        sx={{
          flexShrink: 0,
          width: 36,
          height: 36,
          borderRadius: "50%",
          backgroundColor: canSend ? "primary.main" : "rgba(255, 255, 255, 0.05)",
          color: canSend ? "primary.contrastText" : "rgba(255, 255, 255, 0.28)",
          transition: "background-color 140ms ease",
          "&:hover": {
            backgroundColor: canSend ? "primary.light" : "rgba(255, 255, 255, 0.08)",
          },
        }}
      >
        {isLoading ? (
          <CircularProgress size={16} color="inherit" />
        ) : (
          <SendIcon sx={{ fontSize: 16 }} />
        )}
      </IconButton>
    </Box>
  );
}
