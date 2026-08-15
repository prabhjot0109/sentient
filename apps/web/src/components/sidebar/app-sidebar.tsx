import { useRef, useState, type ChangeEvent } from "react";
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
  const [activeTab, setActiveTab] = useState<"chats" | "sources">("chats");

  const expanded = isMobile || isOpen;
  const sidebarWidth = expanded ? 260 : 60;

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
        alignItems: expanded ? "stretch" : "center",
        borderRight: "1px solid var(--stroke-subtle)",
        transition: "width 0.22s cubic-bezier(0.4, 0, 0.2, 1)",
        overflow: "hidden",
        position: isMobile ? "fixed" : "relative",
        zIndex: 1200,
        py: expanded ? 0 : 2,
        gap: expanded ? 0 : 2,
      }}
    >
      {!expanded ? (
        <>
          {/* Collapsed state: Circular action buttons */}
          <Tooltip title="Expand sidebar" placement="right">
            <IconButton
              onClick={onToggle}
              size="small"
              sx={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                color: "text.secondary",
                "&:hover": { color: "#ffffff", bgcolor: "rgba(255, 255, 255, 0.06)" },
              }}
            >
              <MenuOpenIcon
                sx={{
                  fontSize: 18,
                  transform: "rotate(180deg)",
                }}
              />
            </IconButton>
          </Tooltip>

          <Box sx={{ width: 24, height: "1px", bgcolor: "var(--stroke-subtle)", my: 0.5 }} />

          <Tooltip title="New chat" placement="right">
            <IconButton
              onClick={onNewChat}
              sx={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                border: "1px solid var(--stroke-subtle)",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                color: "text.secondary",
                "&:hover": {
                  color: "#ffffff",
                  borderColor: "rgba(255, 255, 255, 0.15)",
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                },
              }}
            >
              <NewChatIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>

          <Tooltip title="Add source" placement="right">
            <IconButton
              onClick={() => fileInputRef.current?.click()}
              disabled={isUploading}
              sx={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                border: "1px solid var(--stroke-subtle)",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                color: "text.secondary",
                "&:hover": {
                  color: "#ffffff",
                  borderColor: "rgba(255, 255, 255, 0.15)",
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                },
              }}
            >
              {isUploading ? (
                <CircularProgress size={16} color="inherit" />
              ) : (
                <UploadIcon sx={{ fontSize: 18 }} />
              )}
            </IconButton>
          </Tooltip>

          <Box sx={{ flex: 1 }} />

          <Tooltip title="Settings" placement="right">
            <IconButton
              onClick={onOpenSettings}
              sx={{
                width: 40,
                height: 40,
                borderRadius: "50%",
                border: "1px solid var(--stroke-subtle)",
                backgroundColor: "rgba(255, 255, 255, 0.02)",
                color: "text.secondary",
                "&:hover": {
                  color: "#ffffff",
                  borderColor: "rgba(255, 255, 255, 0.15)",
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                },
              }}
            >
              <SettingsIcon sx={{ fontSize: 18 }} />
            </IconButton>
          </Tooltip>
        </>
      ) : (
        <>
          {/* Expanded State Content */}
          {/* Header Row */}
          <Box
            sx={{
              px: 2,
              py: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              gap: 1,
            }}
          >
            <Typography
              variant="subtitle1"
              sx={{ fontWeight: 700, fontSize: "1rem", color: "#ffffff", letterSpacing: "-0.01em" }}
            >
              Sentient
            </Typography>

            <Tooltip title={isMobile ? "Close sidebar" : "Collapse sidebar"} placement="right">
              <IconButton
                onClick={isMobile ? onClose : onToggle}
                size="small"
                sx={{
                  width: 32,
                  height: 32,
                  borderRadius: "8px",
                  color: "text.secondary",
                  "&:hover": { color: "#ffffff", bgcolor: "rgba(255, 255, 255, 0.06)" },
                }}
              >
                {isMobile ? (
                  <CloseIcon sx={{ fontSize: 18 }} />
                ) : (
                  <MenuOpenIcon sx={{ fontSize: 18 }} />
                )}
              </IconButton>
            </Tooltip>
          </Box>

          {/* Tab Navigation */}
          <Box sx={{ px: 2, pb: 2 }}>
            <Box
              sx={{
                display: "flex",
                borderRadius: "8px",
                p: "3px",
                backgroundColor: "rgba(255, 255, 255, 0.03)",
                border: "1px solid rgba(255, 255, 255, 0.06)",
              }}
            >
              <Button
                onClick={() => setActiveTab("chats")}
                sx={{
                  flex: 1,
                  py: 0.5,
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  borderRadius: "6px",
                  minHeight: 28,
                  backgroundColor: activeTab === "chats" ? "rgba(255, 255, 255, 0.08)" : "transparent",
                  color: activeTab === "chats" ? "#ffffff" : "text.secondary",
                  "&:hover": {
                    backgroundColor: activeTab === "chats" ? "rgba(255, 255, 255, 0.1)" : "rgba(255, 255, 255, 0.04)",
                    color: "#ffffff",
                  },
                }}
              >
                Chats
              </Button>
              <Button
                onClick={() => setActiveTab("sources")}
                sx={{
                  flex: 1,
                  py: 0.5,
                  fontSize: "0.78rem",
                  fontWeight: 600,
                  borderRadius: "6px",
                  minHeight: 28,
                  backgroundColor: activeTab === "sources" ? "rgba(255, 255, 255, 0.08)" : "transparent",
                  color: activeTab === "sources" ? "#ffffff" : "text.secondary",
                  "&:hover": {
                    backgroundColor: activeTab === "sources" ? "rgba(255, 255, 255, 0.1)" : "rgba(255, 255, 255, 0.04)",
                    color: "#ffffff",
                  },
                }}
              >
                Knowledge
              </Button>
            </Box>
          </Box>

          {/* Tab Contents */}
          <Box
            sx={{
              flex: 1,
              minHeight: 0,
              display: "flex",
              flexDirection: "column",
              px: 2,
              pb: 2,
              overflowY: "auto",
            }}
          >
            {activeTab === "chats" ? (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, flex: 1, minHeight: 0 }}>
                {/* New Chat Button */}
                <Button
                  fullWidth
                  onClick={onNewChat}
                  startIcon={<NewChatIcon sx={{ fontSize: 16 }} />}
                  sx={{
                    justifyContent: "center",
                    py: 1,
                    borderRadius: "8px",
                    backgroundColor: "#ffffff",
                    color: "#000000",
                    fontWeight: 600,
                    fontSize: "0.85rem",
                    "&:hover": {
                      backgroundColor: "#e2e2e7",
                    },
                  }}
                >
                  New chat
                </Button>

                {/* Chat List */}
                {isChatLoading ? (
                  <Box sx={{ display: "grid", placeItems: "center", py: 4 }}>
                    <CircularProgress size={18} />
                  </Box>
                ) : chats.length > 0 ? (
                  <List sx={{ p: 0, display: "flex", flexDirection: "column", gap: 0.5, overflowY: "auto", flex: 1 }}>
                    {chats.map((chat) => (
                      <Box
                        key={chat.id}
                        sx={{
                          display: "flex",
                          alignItems: "stretch",
                          gap: 0.5,
                          position: "relative",
                          "&:hover .delete-btn": { opacity: 0.7 },
                        }}
                      >
                        <ListItemButton
                          selected={chat.id === activeChatId}
                          onClick={() => void onSelectChat(chat.id)}
                          sx={{
                            borderRadius: "8px",
                            py: 0.75,
                            px: 1.25,
                            backgroundColor:
                              chat.id === activeChatId
                                ? "rgba(255, 255, 255, 0.08)"
                                : "transparent",
                            color: chat.id === activeChatId ? "#ffffff" : "text.secondary",
                            "&:hover": {
                              backgroundColor: "rgba(255, 255, 255, 0.04)",
                              color: "#ffffff",
                            },
                            "&.Mui-selected": {
                              backgroundColor: "rgba(255, 255, 255, 0.08)",
                              "&:hover": {
                                backgroundColor: "rgba(255, 255, 255, 0.1)",
                              },
                            },
                          }}
                        >
                          <ListItemText
                            primary={chat.title}
                            primaryTypographyProps={{
                              noWrap: true,
                              sx: { fontSize: "0.85rem", fontWeight: 500 },
                            }}
                            sx={{ m: 0, pr: 2 }}
                          />
                        </ListItemButton>

                        <IconButton
                          className="delete-btn"
                          onClick={(e) => {
                            e.stopPropagation();
                            void onDeleteChat(chat.id);
                          }}
                          size="small"
                          sx={{
                            position: "absolute",
                            right: 8,
                            top: "50%",
                            transform: "translateY(-50%)",
                            opacity: 0,
                            transition: "opacity 120ms ease, color 120ms ease",
                            color: "text.secondary",
                            backgroundColor: "var(--surface-raised)",
                            "&:hover": {
                              color: "error.main",
                              opacity: "1 !important",
                              backgroundColor: "rgba(255, 255, 255, 0.06)",
                            },
                            zIndex: 2,
                          }}
                        >
                          <CloseIcon sx={{ fontSize: 14 }} />
                        </IconButton>
                      </Box>
                    ))}
                  </List>
                ) : (
                  <Typography
                    variant="body2"
                    sx={{ py: 3, color: "text.secondary", textAlign: "center", fontSize: "0.85rem" }}
                  >
                    No saved chats yet.
                  </Typography>
                )}
              </Box>
            ) : (
              <Box sx={{ display: "flex", flexDirection: "column", gap: 1.5, flex: 1, minHeight: 0 }}>
                {/* Add Source Button */}
                <Button
                  fullWidth
                  variant="outlined"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isUploading}
                  startIcon={
                    isUploading ? (
                      <CircularProgress size={16} color="inherit" />
                    ) : (
                      <UploadIcon sx={{ fontSize: 16 }} />
                    )
                  }
                  sx={{
                    justifyContent: "center",
                    py: 1,
                    borderRadius: "8px",
                    border: "1px dashed rgba(255, 255, 255, 0.15)",
                    color: "text.primary",
                    backgroundColor: "rgba(255, 255, 255, 0.02)",
                    "&:hover": {
                      borderColor: "#ffffff",
                      backgroundColor: "rgba(255, 255, 255, 0.04)",
                    },
                  }}
                >
                  {isUploading ? "Uploading..." : "Add source"}
                </Button>

                {error && (
                  <Alert severity="error" sx={{ py: 0.5, px: 1, fontSize: "0.75rem" }}>
                    {error}
                  </Alert>
                )}

                {/* Source List */}
                {isLoading ? (
                  <Box sx={{ display: "grid", placeItems: "center", py: 4 }}>
                    <CircularProgress size={18} />
                  </Box>
                ) : sources.length === 0 ? (
                  <Typography
                    variant="body2"
                    sx={{ py: 3, color: "text.secondary", textAlign: "center", fontSize: "0.85rem" }}
                  >
                    No sources uploaded yet.
                  </Typography>
                ) : (
                  <List sx={{ p: 0, display: "flex", flexDirection: "column", gap: 0.5, overflowY: "auto", flex: 1 }}>
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
            )}
          </Box>

          {/* Settings Row Pinned to Bottom */}
          <Box
            sx={{
              p: 1.5,
              borderTop: "1px solid var(--stroke-subtle)",
              display: "flex",
              justifyContent: "stretch",
            }}
          >
            <Button
              fullWidth
              onClick={onOpenSettings}
              sx={{
                justifyContent: "flex-start",
                gap: 1.5,
                minWidth: 0,
                width: "100%",
                height: 40,
                py: 1,
                px: 1.5,
                borderRadius: "8px",
                color: "text.primary",
                backgroundColor: "transparent",
                "&:hover": { backgroundColor: "rgba(255, 255, 255, 0.04)" },
              }}
            >
              <SettingsIcon sx={{ fontSize: 18, color: "text.secondary" }} />
              <Typography sx={{ fontSize: "0.85rem", fontWeight: 600, color: "#ffffff" }}>
                Settings
              </Typography>
            </Button>
          </Box>
        </>
      )}

      {/* Hidden File Input (Always in DOM so ref works) */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.txt"
        multiple
        onChange={handleFileSelect}
        style={{ display: "none" }}
      />
    </Box>
  );
}
