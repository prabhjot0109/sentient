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
} from "@mui/material";
import {
  Add as PlusIcon,
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

  if (!isOpen) return null;

  return (
    <Box
      component="aside"
      sx={{
        width: 320,
        height: "100vh",
        backgroundColor: "#0c0c0e",
        display: "flex",
        flexDirection: "column",
        zIndex: 30,
        borderRight: "1px solid rgba(255, 255, 255, 0.05)",
      }}
    >
      {/* Brand Header */}
      <Box
        sx={{
          p: 3,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
        }}
      >
        <Box sx={{ display: "flex", alignItems: "center", gap: 2 }}>
          <Avatar
            sx={{
              width: 40,
              height: 40,
              bgcolor: "primary.main",
              boxShadow: "0 8px 16px rgba(59, 130, 246, 0.25)",
              background: "linear-gradient(135deg, #3b82f6 0%, #2dd4bf 100%)",
            }}
          >
            <SparklesIcon sx={{ color: "white" }} />
          </Avatar>
          <Typography
            variant="h6"
            sx={{ fontWeight: 800, letterSpacing: -1, fontFamily: "Outfit" }}
          >
            Sentient
          </Typography>
        </Box>
        <IconButton
          onClick={onToggle}
          size="small"
          sx={{ color: "text.secondary" }}
        >
          <DrawerIcon sx={{ transform: "rotate(180deg)" }} />
        </IconButton>
      </Box>

      {/* Main Action - NotebookLM style "Add source" */}
      <Box sx={{ px: 2, pb: 4 }}>
        <Button
          fullWidth
          variant="contained"
          size="large"
          startIcon={
            isUploading ? (
              <CircularProgress size={20} color="inherit" />
            ) : (
              <ZapIcon />
            )
          }
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          sx={{
            py: 1.5,
            fontSize: "0.9rem",
            letterSpacing: 0.5,
          }}
        >
          Add Intelligence
        </Button>
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
      <Box sx={{ flex: 1, overflowY: "auto", px: 2 }}>
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
              opacity: 0.5,
              wordSpacing: 2,
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
                "& .MuiBadge-badge": { fontSize: 10, height: 16, minWidth: 16 },
              }}
            />
          )}
        </Box>

        {isLoading ? (
          <Box sx={{ textAlign: "center", py: 8, opacity: 0.3 }}>
            <CircularProgress size={24} sx={{ mb: 2 }} />
            <Typography variant="caption" display="block">
              Scanning cognitive core...
            </Typography>
          </Box>
        ) : sources.length === 0 ? (
          <Box
            onClick={() => fileInputRef.current?.click()}
            sx={{
              p: 4,
              textAlign: "center",
              border: "1px dashed rgba(255, 255, 255, 0.1)",
              borderRadius: 4,
              cursor: "pointer",
              transition: "0.3s",
              "&:hover": {
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                borderColor: "primary.main",
              },
            }}
          >
            <UploadIcon
              sx={{
                fontSize: 40,
                color: "text.secondary",
                mb: 2,
                opacity: 0.2,
              }}
            />
            <Typography
              variant="body2"
              sx={{ color: "text.secondary", fontWeight: 600 }}
            >
              Ingest Document
            </Typography>
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", opacity: 0.5 }}
            >
              PDF or TXT up to 10MB
            </Typography>
          </Box>
        ) : (
          <List sx={{ p: 0 }}>
            {sources.map((source) => (
              <SourceItem
                key={source.path}
                source={source}
                onDelete={() => remove(source.path)}
              />
            ))}
          </List>
        )}
      </Box>

      {/* Footer Settings */}
      <Box sx={{ p: 2, borderTop: "1px solid rgba(255, 255, 255, 0.05)" }}>
        <Button
          fullWidth
          onClick={onOpenSettings}
          sx={{
            justifyContent: "flex-start",
            py: 1.5,
            px: 2,
            backgroundColor: "rgba(255, 255, 255, 0.03)",
            color: "text.primary",
            "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.06)" },
          }}
        >
          <Box sx={{ position: "relative", mr: 2 }}>
            <Avatar
              sx={{
                width: 32,
                height: 32,
                bgcolor: hasApiKey
                  ? "rgba(59, 130, 246, 0.1)"
                  : "rgba(239, 68, 68, 0.1)",
                color: hasApiKey ? "primary.main" : "error.main",
                fontSize: 14,
                fontWeight: 800,
              }}
            >
              {hasApiKey ? "OK" : "!"}
            </Avatar>
            {!hasApiKey && (
              <Box
                sx={{
                  position: "absolute",
                  top: -2,
                  right: -2,
                  width: 10,
                  height: 10,
                  bgcolor: "error.main",
                  borderRadius: "50%",
                  border: "2px solid #0c0c0e",
                }}
              />
            )}
          </Box>
          <Box sx={{ flex: 1, textAlign: "left" }}>
            <Typography sx={{ fontSize: "0.8rem", fontWeight: 700 }}>
              Workspace
            </Typography>
            <Typography
              sx={{
                fontSize: "0.65rem",
                color: "text.secondary",
                fontWeight: 600,
              }}
            >
              {hasApiKey ? "Core Synchronized" : "Action Required"}
            </Typography>
          </Box>
          <SettingsIcon
            sx={{ fontSize: 18, color: "text.secondary", opacity: 0.5 }}
          />
        </Button>
      </Box>
    </Box>
  );
}
