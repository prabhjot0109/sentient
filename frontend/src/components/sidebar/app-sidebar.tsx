import { useRef, type ChangeEvent } from "react";
import {
  Alert,
  Box,
  Button,
  CircularProgress,
  IconButton,
  List,
  ListItemButton,
  ListItemText,
  Tooltip,
  Typography,
} from "@mui/material";
import {
  Close as CloseIcon,
  MenuOpen as MenuOpenIcon,
  NoteAddOutlined as NewChatIcon,
  SettingsOutlined as SettingsIcon,
  UploadFileOutlined as UploadIcon,
} from "@mui/icons-material";
import { SourceItem } from "./source-item";
import { useSources } from "@/hooks/use-sources";
import type { ChatSessionSummary } from "@/types";

interface AppSidebarProps {
  isOpen: boolean;
  isMobile?: boolean;
  onClose?: () => void;
  onToggle: () => void;
  onOpenSettings: () => void;
  hasApiKey: boolean;
  chats: ChatSessionSummary[];
  activeChatId: string | null;
  isChatLoading: boolean;
  onNewChat: () => void;
  onSelectChat: (chatId: string) => void | Promise<void>;
  onDeleteChat: (chatId: string) => void | Promise<void>;
}

export function AppSidebar({
  isOpen,
  isMobile = false,
  onClose,
  onToggle,
  onOpenSettings,
  hasApiKey,
  chats,
  activeChatId,
  isChatLoading,
  onNewChat,
  onSelectChat,
  onDeleteChat,
}: AppSidebarProps) {
  const { sources, isLoading, isUploading, error, upload, remove } =
    useSources();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const expanded = isMobile || isOpen;
  const sidebarWidth = expanded ? 268 : 64;

  const handleFileSelect = async (e: ChangeEvent<HTMLInputElement>) => {
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
        width: sidebarWidth,
        height: "100%",
        minHeight: 0,
        backgroundColor: "var(--surface-raised)",
        display: "flex",
        flexDirection: "column",
        borderRight: "1px solid var(--stroke-subtle)",
        transition: "width 0.24s ease",
        overflow: "hidden",
      }}
    >
      <Box
        sx={{
          px: expanded ? 2 : 1.25,
          py: 1.25,
          display: "flex",
          alignItems: "center",
          justifyContent: expanded ? "space-between" : "center",
          gap: 1,
        }}
      >
        {expanded ? (
          <Box>
            <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
              Sentient
            </Typography>
            <Typography variant="body2" sx={{ color: "text.secondary", fontSize: "0.75rem", lineHeight: 1.2 }}>
              AI NPC • Game Lore Context
            </Typography>
          </Box>
        ) : null}

        <Tooltip
          title={isMobile ? "Close sidebar" : expanded ? "Collapse sidebar" : "Expand sidebar"}
          placement="right"
        >
          <IconButton
            onClick={isMobile ? onClose : onToggle}
            size="small"
            sx={{
              width: 36,
              height: 36,
              borderRadius: 2.5,
              color: "text.secondary",
              border: expanded ? "1px solid transparent" : "1px solid var(--stroke-subtle)",
              backgroundColor: expanded ? "transparent" : "rgba(255, 255, 255, 0.03)",
              "&:hover": { bgcolor: "rgba(255, 255, 255, 0.06)" },
            }}
          >
            {isMobile ? (
              <CloseIcon sx={{ fontSize: 18 }} />
            ) : (
              <MenuOpenIcon
                sx={{
                  fontSize: 18,
                  transform: expanded ? "none" : "rotate(180deg)",
                  transition: "transform 180ms ease",
                }}
              />
            )}
          </IconButton>
        </Tooltip>
      </Box>

      <Box
        sx={{
          px: expanded ? 2 : 1.25,
          pb: 1.5,
          display: "flex",
          flexDirection: "column",
          gap: 1,
          justifyContent: expanded ? "stretch" : "center",
        }}
      >
        {expanded ? (
          <Button
            fullWidth
            variant="contained"
            onClick={onNewChat}
            startIcon={<NewChatIcon />}
            sx={{ justifyContent: "flex-start" }}
          >
            New chat
          </Button>
        ) : (
          <Tooltip title="New chat" placement="right">
            <IconButton
              onClick={onNewChat}
              sx={{
                width: 36,
                height: 36,
                borderRadius: 2.5,
                color: "primary.contrastText",
                bgcolor: "primary.main",
                "&:hover": { bgcolor: "primary.light" },
              }}
            >
              <NewChatIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        )}

        {expanded ? (
          <Button
            fullWidth
            variant="outlined"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            startIcon={
              isUploading ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <UploadIcon />
              )
            }
            sx={{
              justifyContent: "flex-start",
              backgroundColor: "rgba(255, 255, 255, 0.02)",
            }}
          >
            {isUploading ? "Uploading" : "Add source"}
          </Button>
        ) : (
          <Tooltip title="Add source" placement="right">
            <IconButton
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              sx={{
                width: 36,
                height: 36,
                borderRadius: 2.5,
                border: "1px solid var(--stroke-subtle)",
                color: "text.primary",
                bgcolor: "rgba(255, 255, 255, 0.03)",
                "&:hover": { bgcolor: "rgba(255, 255, 255, 0.06)" },
              }}
            >
              {isUploading ? (
                <CircularProgress size={18} color="inherit" />
              ) : (
                <UploadIcon />
              )}
            </IconButton>
          </Tooltip>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,.txt"
          multiple
          onChange={handleFileSelect}
          style={{ display: "none" }}
        />
      </Box>

      <Box
        sx={{
          px: expanded ? 1.5 : 1.25,
          pb: 1.5,
          minHeight: 0,
        }}
      >
        {expanded ? (
          <Box
            sx={{
              px: 0.5,
              mb: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Typography variant="overline" sx={{ color: "text.secondary" }}>
              Chats
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              {chats.length}
            </Typography>
          </Box>
        ) : null}

        {isChatLoading && expanded ? (
          <Box sx={{ textAlign: "center", py: 2 }}>
            <CircularProgress size={18} />
          </Box>
        ) : chats.length > 0 ? (
          <List
            sx={{
              p: 0,
              display: "flex",
              flexDirection: "column",
              gap: 0.5,
              maxHeight: expanded ? 220 : 0,
              overflowY: expanded ? "auto" : "hidden",
            }}
          >
            {chats.map((chat) => (
              <Box
                key={chat.id}
                sx={{
                  display: "flex",
                  alignItems: "stretch",
                  gap: 0.5,
                }}
              >
                <ListItemButton
                  selected={chat.id === activeChatId}
                  onClick={() => void onSelectChat(chat.id)}
                  sx={{
                    borderRadius: 2,
                    border: "1px solid transparent",
                    alignItems: "flex-start",
                    py: 1,
                    px: 1,
                    backgroundColor:
                      chat.id === activeChatId
                        ? "rgba(255, 255, 255, 0.06)"
                        : "transparent",
                    borderColor:
                      chat.id === activeChatId
                        ? "rgba(255, 255, 255, 0.1)"
                        : "transparent",
                    "&:hover": {
                      backgroundColor: "rgba(255, 255, 255, 0.04)",
                    },
                  }}
                >
                  <ListItemText
                    primary={chat.title}
                    secondary={chat.preview || "No messages yet"}
                    primaryTypographyProps={{
                      noWrap: true,
                      sx: { fontSize: "0.84rem", fontWeight: 600 },
                    }}
                    secondaryTypographyProps={{
                      noWrap: true,
                      sx: { fontSize: "0.72rem", color: "text.secondary" },
                    }}
                    sx={{ m: 0 }}
                  />
                </ListItemButton>

                <IconButton
                  onClick={() => void onDeleteChat(chat.id)}
                  sx={{
                    alignSelf: "center",
                    width: 32,
                    height: 32,
                    color: "text.secondary",
                    "&:hover": { color: "error.main" },
                  }}
                >
                  <CloseIcon sx={{ fontSize: 16 }} />
                </IconButton>
              </Box>
            ))}
          </List>
        ) : expanded ? (
          <Typography variant="body2" sx={{ px: 0.5, py: 0.5, color: "text.secondary" }}>
            No saved chats yet.
          </Typography>
        ) : null}
      </Box>

      <Box
        sx={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          px: expanded ? 1.5 : 1.25,
          pb: 1.5,
        }}
      >
        {expanded ? (
          <Box
            sx={{
              px: 0.5,
              mb: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <Typography variant="overline" sx={{ color: "text.secondary" }}>
              Sources
            </Typography>
            <Typography variant="caption" sx={{ color: "text.secondary" }}>
              {sources.length}
            </Typography>
          </Box>
        ) : (
          <Typography
            variant="caption"
            sx={{
              display: "block",
              textAlign: "center",
              mb: 1.25,
              color: "text.secondary",
              fontWeight: 600,
            }}
          >
            {sources.length}
          </Typography>
        )}

        {error && expanded && (
          <Alert severity="error" sx={{ mb: 1 }}>
            {error}
          </Alert>
        )}

        {isLoading ? (
          <Box sx={{ textAlign: "center", py: 5 }}>
            <CircularProgress size={22} />
          </Box>
        ) : sources.length === 0 ? (
          expanded ? (
            <Typography
              variant="body2"
              sx={{ px: 0.5, py: 1, color: "text.secondary" }}
            >
              No sources yet.
            </Typography>
          ) : null
        ) : (
          <List
            sx={{
              p: 0,
              display: "flex",
              flexDirection: "column",
              gap: 0.5,
            }}
          >
            {sources.map((source) => (
              <SourceItem
                key={source.path}
                source={source}
                onDelete={() => remove(source.path)}
                isCollapsed={!expanded}
              />
            ))}
          </List>
        )}
      </Box>

      <Box
        sx={{
          p: expanded ? 1.5 : 1.25,
          borderTop: "1px solid var(--stroke-subtle)",
          display: "flex",
          justifyContent: expanded ? "stretch" : "center",
        }}
      >
        <Tooltip title={!expanded ? "Workspace settings" : ""} placement="right">
          <Button
            fullWidth
            onClick={onOpenSettings}
            sx={{
              justifyContent: expanded ? "flex-start" : "center",
              gap: expanded ? 1 : 0,
              minWidth: 0,
              width: expanded ? "100%" : 36,
              height: expanded ? 40 : 36,
              py: expanded ? 1 : 0,
              px: expanded ? 1 : 0,
              borderRadius: 2.5,
              color: hasApiKey ? "text.primary" : "text.secondary",
              border: expanded ? "none" : "1px solid var(--stroke-subtle)",
              backgroundColor: expanded ? "transparent" : "rgba(255, 255, 255, 0.03)",
              "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.05)" },
            }}
          >
            <SettingsIcon sx={{ fontSize: 18 }} />
            {expanded && (
              <Box sx={{ textAlign: "left" }}>
                <Typography sx={{ fontSize: "0.88rem", fontWeight: 600 }}>
                  Settings
                </Typography>
                <Typography sx={{ fontSize: "0.74rem", color: "text.secondary" }}>
                  {hasApiKey ? "API key connected" : "API key needed"}
                </Typography>
              </Box>
            )}
          </Button>
        </Tooltip>
      </Box>
    </Box>
  );
}
