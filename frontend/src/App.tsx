import { useEffect, useState } from "react";
import { Box, Drawer, useMediaQuery, useTheme } from "@mui/material";
import { AppSidebar } from "@/components/sidebar";
import { ChatContainer } from "@/components/chat";
import { SettingsDialog } from "@/components/settings";
import { useChat } from "@/hooks/use-chat";
import { useSettings } from "@/hooks/use-settings";

export default function App() {
  const muiTheme = useTheme();
  const isMobile = useMediaQuery(muiTheme.breakpoints.down("md"));
  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { apiKey, setApiKey, hasApiKey } = useSettings();
  const {
    chats,
    activeChatId,
    messages,
    isLoading,
    isHistoryLoading,
    error,
    sendMessage,
    clearMessages,
    loadChat,
    removeChat,
  } = useChat();

  useEffect(() => {
    setSidebarOpen(!isMobile);
  }, [isMobile]);

  return (
    <Box
      sx={{
        display: "flex",
        height: "100dvh",
        bgcolor: "background.default",
        color: "text.primary",
        overflow: "hidden",
      }}
    >
      {!isMobile && (
        <AppSidebar
          apiKey={apiKey}
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen((open) => !open)}
          onOpenSettings={() => setSettingsOpen(true)}
          hasApiKey={hasApiKey}
          chats={chats}
          activeChatId={activeChatId}
          isChatLoading={isHistoryLoading}
          onNewChat={clearMessages}
          onSelectChat={loadChat}
          onDeleteChat={removeChat}
        />
      )}

      {isMobile && (
        <Drawer
          open={sidebarOpen}
          onClose={() => setSidebarOpen(false)}
          PaperProps={{
            sx: {
              width: 288,
              maxWidth: "100vw",
              backgroundColor: "var(--surface-raised)",
              boxShadow: "none",
              p: 0,
            },
          }}
        >
          <AppSidebar
            apiKey={apiKey}
            isOpen
            isMobile
            onClose={() => setSidebarOpen(false)}
            onToggle={() => setSidebarOpen(false)}
            onOpenSettings={() => setSettingsOpen(true)}
            hasApiKey={hasApiKey}
            chats={chats}
            activeChatId={activeChatId}
            isChatLoading={isHistoryLoading}
            onNewChat={() => {
              clearMessages();
              setSidebarOpen(false);
            }}
            onSelectChat={async (chatId) => {
              await loadChat(chatId);
              setSidebarOpen(false);
            }}
            onDeleteChat={removeChat}
          />
        </Drawer>
      )}

      <Box
        component="main"
        sx={{
          flex: 1,
          display: "flex",
          minWidth: 0,
          minHeight: 0,
          height: "100%",
          overflow: "hidden",
        }}
      >
        <ChatContainer
          apiKey={apiKey}
          hasApiKey={hasApiKey}
          isMobile={isMobile}
          onOpenSettings={() => setSettingsOpen(true)}
          onToggleSidebar={() => setSidebarOpen((open) => !open)}
          messages={messages}
          isLoading={isLoading}
          isHistoryLoading={isHistoryLoading}
          error={error}
          onSend={sendMessage}
          activeChatId={activeChatId}
          activeChatTitle={
            chats.find((chat) => chat.id === activeChatId)?.title ?? "Sentient"
          }
        />
      </Box>

      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        apiKey={apiKey}
        onSaveApiKey={setApiKey}
      />
    </Box>
  );
}
