import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  IconButton,
  InputAdornment,
  Stack,
  TextField,
  Typography,
} from "@mui/material";
import {
  CheckCircleOutlined as CheckIcon,
  InfoOutlined as InfoIcon,
  KeyOutlined as KeyIcon,
  Visibility as EyeIcon,
  VisibilityOff as EyeOffIcon,
} from "@mui/icons-material";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  apiKey: string;
  onSaveApiKey: (key: string) => void;
}

export function SettingsDialog({
  open,
  onOpenChange,
  apiKey,
  onSaveApiKey,
}: SettingsDialogProps) {
  const [inputValue, setInputValue] = useState(apiKey);
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (open) {
      setInputValue(apiKey);
      setSaved(false);
    }
  }, [apiKey, open]);

  const handleClose = () => {
    setInputValue(apiKey);
    setSaved(false);
    onOpenChange(false);
  };

  const handleSave = () => {
    onSaveApiKey(inputValue);
    setSaved(true);
    setTimeout(() => {
      onOpenChange(false);
    }, 1000);
  };

  return (
    <Dialog
      open={open}
      onClose={handleClose}
      PaperProps={{
        sx: {
          width: "100%",
          maxWidth: 500,
          p: 1,
        },
      }}
    >
      <DialogContent>
        <Stack spacing={3}>
          <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
                Workspace settings
              </Typography>
              <Typography
                variant="body2"
                sx={{ color: "text.secondary", maxWidth: 360 }}
              >
                Store your OpenRouter or OpenAI API key locally in this browser so
                Sentient can send chat and retrieval requests.
              </Typography>
            </Box>
            <Box
              sx={{
                width: 48,
                height: 48,
                display: "grid",
                placeItems: "center",
                borderRadius: 2,
                bgcolor: "rgba(255, 255, 255, 0.02)",
                color: apiKey ? "text.primary" : "text.secondary",
                flexShrink: 0,
              }}
            >
              <KeyIcon />
            </Box>
          </Box>

          <TextField
            fullWidth
            type={showKey ? "text" : "password"}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setSaved(false);
            }}
            label="OpenRouter / OpenAI API Key"
            placeholder="sk-..."
            variant="outlined"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <KeyIcon sx={{ color: "text.secondary", opacity: 0.7 }} />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowKey((value) => !value)}
                    edge="end"
                    size="small"
                  >
                    {showKey ? <EyeOffIcon /> : <EyeIcon />}
                  </IconButton>
                </InputAdornment>
              ),
              sx: {
                borderRadius: 2,
                fontFamily: '"IBM Plex Mono", monospace',
                fontSize: "0.82rem",
              },
            }}
          />

          <Alert icon={<InfoIcon fontSize="inherit" />} severity="info">
            Your key is stored locally in browser storage. It is not persisted by
            this frontend to any external service.
          </Alert>

          {saved && (
            <Alert icon={<CheckIcon />} severity="success">
              API key saved locally.
            </Alert>
          )}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 0, justifyContent: "space-between" }}>
        <Button
          color="inherit"
          onClick={() => {
            setInputValue("");
            onSaveApiKey("");
            setSaved(false);
          }}
          sx={{ color: "text.secondary" }}
        >
          Remove key
        </Button>
        <Box sx={{ display: "flex", gap: 1.5 }}>
          <Button onClick={handleClose} sx={{ color: "text.secondary" }}>
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={!inputValue || saved}
            sx={{ px: 3 }}
          >
            {saved ? "Saved" : "Save key"}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
}
