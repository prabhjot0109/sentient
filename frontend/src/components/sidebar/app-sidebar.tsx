import { useRef } from "react";
import {
  Box,
  Typography,
  Button,
  IconButton,
  Divider,
  List,
  CircularProgress,
  Avatar,
  Badge,
  Tooltip,
} from "@mui/material";
import {
  Settings as SettingsIcon,
  AutoAwesome as SparklesIcon,
  Bolt as ZapIcon,
  CloudUpload as UploadIcon,
  KeyboardTab as DrawerIcon,
} from "@mui/icons-material";
import { SourceItem } from "./source-item";
import { useSources } from "@/hooks/use-sources";

interface AppSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onOpenSettings: () => void;
  hasApiKey: boolean;
}

export function AppSidebar({
  isOpen,
  onToggle,
  onOpenSettings,
  hasApiKey,
}: AppSidebarProps) {
  const { sources, isLoading, isUploading, upload, remove } = useSources();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      for (const file of Array.from(files)) {
        await upload(file);
      }
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <Box
      component="aside"
      sx={{
        width: isOpen ? 320 : 88,
        height: "100vh",
        backgroundColor: "#0c0c0e",
        display: "flex",
        flexDirection: "column",
        zIndex: 30,
        borderRight: "1px solid rgba(255, 255, 255, 0.06)",
        transition: "width 0.3s cubic-bezier(0.4, 0, 0.2, 1)",
        overflow: "hidden",
        position: "relative",
      }}
    >
      {/* Brand Header */}
      <Box
        sx={{
          p: isOpen ? 3 : 2,
          display: "flex",
          alignItems: "center",
          justifyContent: isOpen ? "space-between" : "center",
          minHeight: 88,
        }}
      >
        <Box
          sx={{
            display: "flex",
            alignItems: "center",
            gap: 2,
            overflow: "hidden",
          }}
        >
          <Avatar
            sx={{
              width: 44,
              height: 44,
              bgcolor: "primary.main",
              boxShadow: "0 10px 20px rgba(59, 130, 246, 0.2)",
              background: "linear-gradient(135deg, #3b82f6 0%, #2dd4bf 100%)",
              flexShrink: 0,
            }}
          >
            <SparklesIcon sx={{ color: "white", fontSize: 24 }} />
          </Avatar>
          {isOpen && (
            <Typography
              variant="h6"
              sx={{
                fontWeight: 800,
                letterSpacing: -0.5,
                fontFamily: "Outfit",
                whiteSpace: "nowrap",
              }}
            >
              Sentient
            </Typography>
          )}
        </Box>
        {isOpen && (
          <IconButton
            onClick={onToggle}
            size="small"
            sx={{
              color: "text.secondary",
              bgcolor: "rgba(255, 255, 255, 0.03)",
              "&:hover": { bgcolor: "rgba(255, 255, 255, 0.08)" },
            }}
          >
            <DrawerIcon sx={{ transform: "rotate(180deg)", fontSize: 20 }} />
          </IconButton>
        )}
      </Box>

      {/* Main Action - NotebookLM style "Add source" */}
      <Box sx={{ px: isOpen ? 2 : 1.5, pb: 4 }}>
        <Tooltip title={!isOpen ? "Add Intelligence" : ""} placement="right">
          <Button
            fullWidth
            variant="contained"
            size="large"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            sx={{
              py: isOpen ? 1.5 : 2,
              minWidth: 0,
              display: "flex",
              justifyContent: isOpen ? "flex-start" : "center",
              px: isOpen ? 2.5 : 0,
              borderRadius: 4,
            }}
          >
            {isUploading ? (
              <CircularProgress size={20} color="inherit" />
            ) : (
              <ZapIcon />
            )}
            {isOpen && (
              <Typography sx={{ ml: 1.5, fontWeight: 700, fontSize: "0.9rem" }}>
                Add Intelligence
              </Typography>
            )}
          </Button>
        </Tooltip>
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          multiple
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />
      </Box>

      {/* Sources Body */}
      <Box sx={{ flex: 1, overflowY: "auto", px: isOpen ? 2 : 1.5 }}>
        {isOpen ? (
          <Box
            sx={{
              px: 1,
              mb: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Typography
              variant="overline"
              sx={{
                fontWeight: 900,
                color: "text.secondary",
                opacity: 0.4,
                letterSpacing: 1,
                fontSize: "0.65rem",
              }}
            >
              Knowledge Assets
            </Typography>
            {sources.length > 0 && (
              <Badge
                badgeContent={sources.length}
                color="primary"
                sx={{
                  "& .MuiBadge-badge": {
                    fontSize: 10,
                    height: 16,
                    minWidth: 16,
                  },
                }}
              />
            )}
          </Box>
        ) : (
          <Box sx={{ display: "flex", justifyContent: "center", mb: 2 }}>
            <Divider sx={{ width: 24, borderColor: "rgba(255,255,255,0.1)" }} />
          </Box>
        )}

        {isLoading ? (
          <Box sx={{ textAlign: "center", py: 8, opacity: 0.3 }}>
            <CircularProgress size={24} sx={{ mb: 2 }} />
          </Box>
        ) : sources.length === 0 ? (
          isOpen && (
            <Box
              onClick={() => fileInputRef.current?.click()}
              sx={{
                p: 4,
                textAlign: "center",
                border: "1px dashed rgba(255, 255, 255, 0.1)",
                borderRadius: 5,
                cursor: "pointer",
                transition: "all 0.2s",
                "&:hover": {
                  backgroundColor: "rgba(255, 255, 255, 0.02)",
                  borderColor: "primary.main",
                  transform: "scale(0.98)",
                },
              }}
            >
              <UploadIcon
                sx={{
                  fontSize: 32,
                  color: "text.secondary",
                  mb: 1.5,
                  opacity: 0.3,
                }}
              />
              <Typography
                variant="body2"
                sx={{
                  color: "text.secondary",
                  fontWeight: 700,
                  fontSize: "0.8rem",
                }}
              >
                Ingest
              </Typography>
            </Box>
          )
        ) : (
          <List
            sx={{
              p: 0,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              gap: 1,
            }}
          >
            {sources.map((source) => (
              <SourceItem
                key={source.path}
                source={source}
                onDelete={() => remove(source.path)}
                isCollapsed={!isOpen}
              />
            ))}
          </List>
        )}
      </Box>

      {/* Footer Settings */}
      <Box
        sx={{
          p: isOpen ? 2 : 1.5,
          borderTop: "1px solid rgba(255, 255, 255, 0.06)",
        }}
      >
        <Tooltip title={!isOpen ? "Workspace Settings" : ""} placement="right">
          <Button
            fullWidth
            onClick={onOpenSettings}
            sx={{
              justifyContent: isOpen ? "flex-start" : "center",
              py: 2,
              px: isOpen ? 2 : 0,
              borderRadius: 4,
              backgroundColor: "rgba(255, 255, 255, 0.04)",
              color: "text.primary",
              minWidth: 0,
              "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.08)" },
            }}
          >
            <Box sx={{ position: "relative", mr: isOpen ? 2 : 0 }}>
              <Avatar
                sx={{
                  width: 36,
                  height: 36,
                  bgcolor: hasApiKey
                    ? "rgba(59, 130, 246, 0.15)"
                    : "rgba(239, 68, 68, 0.15)",
                  color: hasApiKey ? "primary.main" : "#ef4444",
                  fontSize: 14,
                  fontWeight: 800,
                  border: `1px solid ${
                    hasApiKey
                      ? "rgba(59, 130, 246, 0.2)"
                      : "rgba(239, 68, 68, 0.2)"
                  }`,
                }}
              >
                {hasApiKey ? "OK" : "!"}
              </Avatar>
            </Box>
            {isOpen && (
              <Box sx={{ flex: 1, textAlign: "left", overflow: "hidden" }}>
                <Typography
                  sx={{
                    fontSize: "0.85rem",
                    fontWeight: 800,
                    whiteSpace: "nowrap",
                  }}
                >
                  Workspace
                </Typography>
                <Typography
                  sx={{
                    fontSize: "0.7rem",
                    color: "text.secondary",
                    fontWeight: 600,
                    opacity: 0.6,
                    whiteSpace: "nowrap",
                  }}
                >
                  {hasApiKey ? "Core Synchronized" : "Action Required"}
                </Typography>
              </Box>
            )}
            {isOpen && (
              <SettingsIcon
                sx={{ fontSize: 18, color: "text.secondary", opacity: 0.4 }}
              />
            )}
          </Button>
        </Tooltip>
      </Box>

      {/* Collapse Toggle when closed - floating feel */}
      {!isOpen && (
        <IconButton
          onClick={onToggle}
          size="small"
          sx={{
            position: "absolute",
            top: 104, // Below the Add button
            left: "50%",
            transform: "translateX(-50%)",
            color: "text.secondary",
            bgcolor: "rgba(255, 255, 255, 0.03)",
            zIndex: 40,
            "&:hover": { bgcolor: "rgba(255, 255, 255, 0.08)" },
          }}
        >
          <DrawerIcon sx={{ fontSize: 16 }} />
        </IconButton>
      )}
    </Box>
  );
}
