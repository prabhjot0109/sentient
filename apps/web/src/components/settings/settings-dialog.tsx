import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  Stack,
  Typography,
} from "@mui/material";
import {
  AutoAwesomeOutlined as PersonaIcon,
  CircleOutlined as OfflineIcon,
  FiberManualRecord as OnlineIcon,
} from "@mui/icons-material";
import { checkHealth, type HealthResponse } from "@/lib/api";

interface SettingsDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function SettingsDialog({ open, onOpenChange }: SettingsDialogProps) {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    checkHealth()
      .then((data) => {
        if (!cancelled) setHealth(data);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(
            err instanceof Error ? err.message : "Failed to reach the backend"
          );
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open]);

  const online = health?.status === "online";
  const chunkCount = health?.index_metadata?.chunk_count;

  return (
    <Dialog
      open={open}
      onClose={() => onOpenChange(false)}
      PaperProps={{ sx: { width: "100%", maxWidth: 500, p: 1 } }}
    >
      <DialogContent>
        <Stack spacing={3}>
          <Box sx={{ display: "flex", justifyContent: "space-between", gap: 2 }}>
            <Box>
              <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
                Workspace
              </Typography>
              <Typography
                variant="body2"
                sx={{ color: "text.secondary", maxWidth: 360 }}
              >
                Live status from the backend. The model and API key are configured
                on the server (<code>.env</code>) — nothing to enter here.
              </Typography>
            </Box>
            <Chip
              size="small"
              icon={
                online ? (
                  <OnlineIcon sx={{ fontSize: 12 }} />
                ) : (
                  <OfflineIcon sx={{ fontSize: 12 }} />
                )
              }
              label={online ? "Online" : "Offline"}
              color={online ? "success" : "default"}
              variant="outlined"
              sx={{ height: 26, flexShrink: 0 }}
            />
          </Box>

          {error && <Alert severity="error">{error}</Alert>}

          {isLoading ? (
            <Box sx={{ display: "grid", placeItems: "center", py: 4 }}>
              <CircularProgress size={22} />
            </Box>
          ) : health ? (
            <Stack spacing={1.5}>
              {health.persona && (
                <Box
                  sx={{
                    display: "flex",
                    alignItems: "center",
                    gap: 1,
                    p: 1.5,
                    borderRadius: 2,
                    border: "1px solid var(--stroke-subtle)",
                    backgroundColor: "rgba(255, 255, 255, 0.03)",
                  }}
                >
                  <PersonaIcon sx={{ fontSize: 18, color: "text.secondary" }} />
                  <Box>
                    <Typography
                      variant="caption"
                      sx={{ color: "text.secondary", display: "block" }}
                    >
                      Active persona
                    </Typography>
                    <Typography sx={{ fontSize: "0.9rem", fontWeight: 600 }}>
                      {health.persona}
                    </Typography>
                  </Box>
                </Box>
              )}

              <StatusRow label="Model" value={health.llm_model} />
              <StatusRow label="Provider" value={health.llm_provider} />
              <StatusRow label="Embeddings" value={health.embedding_model} />
              <StatusRow label="Search" value={health.search_type} />
              <StatusRow label="Top K" value={health.top_k?.toString()} />
              <StatusRow
                label="Sources"
                value={health.source_count?.toString()}
              />
              <StatusRow
                label="Indexed chunks"
                value={chunkCount?.toString() ?? (health.index_loaded ? "—" : "0")}
              />
              <StatusRow label="Chat storage" value={health.chat_storage} />
            </Stack>
          ) : null}
        </Stack>
      </DialogContent>

      <DialogActions sx={{ p: 3, pt: 0, justifyContent: "flex-end" }}>
        <Button onClick={() => onOpenChange(false)} sx={{ color: "text.secondary" }}>
          Close
        </Button>
      </DialogActions>
    </Dialog>
  );
}

function StatusRow({ label, value }: { label: string; value?: string | null }) {
  return (
    <Box
      sx={{
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
        gap: 2,
        py: 0.75,
        borderBottom: "1px solid var(--stroke-subtle)",
        "&:last-of-type": { borderBottom: "none" },
      }}
    >
      <Typography variant="body2" sx={{ color: "text.secondary" }}>
        {label}
      </Typography>
      <Typography
        variant="body2"
        sx={{
          fontWeight: 600,
          fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
          fontSize: "0.82rem",
          textAlign: "right",
          wordBreak: "break-word",
        }}
      >
        {value || "—"}
      </Typography>
    </Box>
  );
}
