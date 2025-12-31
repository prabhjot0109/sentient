import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogActions,
  Typography,
  TextField,
  Button,
  IconButton,
  InputAdornment,
  Box,
  Avatar,
  Stack,
  Alert,
} from "@mui/material";
import {
  Visibility as Eye,
  VisibilityOff as EyeOff,
  CheckCircle as Check,
  InfoOutlined as AlertCircle,
  ShieldOutlined as ShieldCheck,
  VpnKeyOutlined as Key,
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
          maxWidth: 450,
          p: 2,
          borderRadius: 6,
          backgroundColor: "#121215",
          border: "1px solid rgba(255, 255, 255, 0.08)",
        },
      }}
    >
      <DialogContent>
        <Stack spacing={4} sx={{ alignItems: "center", textAlign: "center" }}>
          <Avatar
            sx={{ width: 64, height: 64, bgcolor: "primary.main", mb: 1 }}
          >
            <ShieldCheck sx={{ fontSize: 32, color: "white" }} />
          </Avatar>

          <Box>
            <Typography variant="h5" sx={{ fontWeight: 800, mb: 1 }}>
              Secure Authentication
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary" }}>
              Interface with the Sentient Neural Engine by providing your OpenAI
              API credentials.
            </Typography>
          </Box>

          <TextField
            fullWidth
            type={showKey ? "text" : "password"}
            value={inputValue}
            onChange={(e) => {
              setInputValue(e.target.value);
              setSaved(false);
            }}
            label="OpenAI API Key"
            placeholder="sk-..."
            variant="outlined"
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <Key sx={{ color: "text.secondary", opacity: 0.5 }} />
                </InputAdornment>
              ),
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={() => setShowKey(!showKey)}
                    edge="end"
                    size="small"
                  >
                    {showKey ? <EyeOff /> : <Eye />}
                  </IconButton>
                </InputAdornment>
              ),
              sx: {
                borderRadius: 4,
                fontFamily: "monospace",
                fontSize: "0.8rem",
              },
            }}
          />

          <Alert
            icon={<AlertCircle fontSize="inherit" />}
            severity="info"
            sx={{
              width: "100%",
              borderRadius: 3,
              backgroundColor: "rgba(59, 130, 246, 0.05)",
              color: "primary.light",
              "& .MuiAlert-icon": { color: "primary.light" },
            }}
          >
            Keys are stored offline in your browser's local state and are never
            exposed to external servers.
          </Alert>

          {saved && (
            <Alert
              icon={<Check />}
              severity="success"
              sx={{ width: "100%", borderRadius: 3 }}
            >
              Credentials encrypted and saved.
            </Alert>
          )}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ p: 4, pt: 0, justifyContent: "space-between" }}>
        <Button
          color="error"
          size="small"
          onClick={() => {
            setInputValue("");
            onSaveApiKey("");
          }}
          sx={{ fontWeight: 700, opacity: 0.6 }}
        >
          Purge Key
        </Button>
        <Box sx={{ display: "flex", gap: 1.5 }}>
          <Button
            onClick={handleClose}
            sx={{ color: "text.secondary", fontWeight: 700 }}
          >
            Cancel
          </Button>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={!inputValue || saved}
            sx={{ borderRadius: 3, px: 4 }}
          >
            {saved ? "Linked" : "Connect"}
          </Button>
        </Box>
      </DialogActions>
    </Dialog>
  );
}
