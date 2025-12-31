import { useState, useRef, useEffect, KeyboardEvent } from "react";
import { 
  Box, 
  InputBase, 
  IconButton, 
  CircularProgress,
  Tooltip
} from "@mui/material";
import { 
  ArrowUpward as SendIcon, 
  KeyboardCommandKey as CommandIcon 
} from "@mui/icons-material";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading?: boolean;
  disabled?: boolean;
}

export function ChatInput({ onSend, isLoading = false, disabled = false }: ChatInputProps) {
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
    <Box sx={{ display: 'flex', alignItems: 'flex-end', gap: 1.5, position: 'relative' }}>
      <InputBase
        multiline
        fullWidth
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Query your research brain..."
        disabled={isLoading || disabled}
        sx={{
          flex: 1,
          px: 1,
          py: 0.5,
          color: 'text.primary',
          fontSize: '1rem',
          lineHeight: 1.5,
          '& .MuiInputBase-input': {
            '&::placeholder': {
              color: 'text.secondary',
              opacity: 0.5,
              fontStyle: 'italic'
            },
          },
        }}
        inputProps={{
          ref: inputRef,
          style: { maxHeight: '200px' }
        }}
      />
      
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.5 }}>
        <Box sx={{ 
          display: { xs: 'none', md: 'flex' }, 
          alignItems: 'center', 
          gap: 0.5, 
          px: 1, 
          py: 0.5, 
          borderRadius: 2, 
          border: '1px solid rgba(255, 255, 255, 0.05)',
          backgroundColor: 'rgba(255, 255, 255, 0.02)',
          opacity: input.trim() ? 1 : 0.3,
          transition: '0.3s'
        }}>
          <CommandIcon sx={{ fontSize: 10, color: 'text.secondary' }} />
          <Box component="span" sx={{ fontSize: 9, fontWeight: 900, color: 'text.secondary', tracking: 1 }}>ENTER</Box>
        </Box>

        <Tooltip title="Send message">
          <IconButton 
            onClick={handleSubmit}
            disabled={!canSend}
            sx={{ 
              width: 40, 
              height: 40, 
              borderRadius: 3,
              backgroundColor: canSend ? 'primary.main' : 'rgba(255, 255, 255, 0.03)',
              color: canSend ? 'white' : 'text.secondary',
              transition: '0.2s',
              '&:hover': {
                backgroundColor: canSend ? 'primary.dark' : 'rgba(255, 255, 255, 0.05)',
                transform: canSend ? 'translateY(-2px)' : 'none'
              },
              '&:active': { transform: 'scale(0.95)' }
            }}
          >
            {isLoading ? <CircularProgress size={18} color="inherit" /> : <SendIcon fontSize="small" />}
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}
