import { useRef, useState, type KeyboardEvent } from "react";
import { Box, CircularProgress, IconButton, InputBase } from "@mui/material";
import { ArrowUpward as SendIcon } from "@mui/icons-material";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  placeholder?: string;
}

export function ChatInput({
  onSend,
  isLoading = false,
  placeholder = "Message Sentient",
}: ChatInputProps) {
  const [input, setInput] = useState("");
  const inputRef = useRef<HTMLTextAreaElement | HTMLInputElement>(null);

  const handleSubmit = () => {
    if (input.trim() && !isLoading) {
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

  const canSend = Boolean(input.trim()) && !isLoading;

  return (
    <Box
      sx={{
        display: "flex",
        alignItems: "flex-end",
        gap: 1,
        borderRadius: "16px",
        pl: 2.5,
        pr: 1.5,
        py: 0.75,
        border: "1px solid rgba(255, 255, 255, 0.12)",
        backgroundColor: "#171717",
        boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)",
        transition: "border-color 160ms ease, background-color 160ms ease",
        "&:focus-within": {
          borderColor: "rgba(255, 255, 255, 0.24)",
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
        disabled={isLoading}
        sx={{
          flex: 1,
          py: 1,
          color: "text.primary",
          fontSize: "1rem",
          lineHeight: 1.5,
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
          width: 32,
          height: 32,
          borderRadius: "50%",
          backgroundColor: canSend ? "#ffffff" : "rgba(255, 255, 255, 0.04)",
          color: canSend ? "#000000" : "rgba(255, 255, 255, 0.15)",
          transition: "background-color 140ms ease, color 140ms ease",
          mb: 0.5,
          "&:hover": {
            backgroundColor: canSend ? "#e2e2e7" : "rgba(255, 255, 255, 0.04)",
          },
          "&.Mui-disabled": {
            backgroundColor: "rgba(255, 255, 255, 0.04)",
            color: "rgba(255, 255, 255, 0.15)",
          }
        }}
      >
        {isLoading ? (
          <CircularProgress size={14} color="inherit" />
        ) : (
          <SendIcon sx={{ fontSize: 15 }} />
        )}
      </IconButton>
    </Box>
  );
}
