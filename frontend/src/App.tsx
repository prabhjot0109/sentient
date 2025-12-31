import { useState } from "react";
import { Box } from "@mui/material";
import { AppSidebar } from "@/components/sidebar";
import { ChatContainer } from "@/components/chat";
import { SettingsDialog } from "@/components/settings";
import { useSettings } from "@/hooks/use-settings";

export default function App() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { apiKey, setApiKey, hasApiKey } = useSettings();

  return (
    <Box sx={{ 
      display: 'flex', 
      height: '100vh', 
      bgcolor: 'background.default',
      color: 'text.primary',
      overflow: 'hidden',
      position: 'relative'
    }}>
      {/* Background Ambience */}
      <Box sx={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        opacity: 0.2,
        zIndex: 0,
        overflow: 'hidden'
      }}>
        <Box sx={{
          position: 'absolute',
          top: '-10%',
          left: '-10%',
          width: '50%',
          height: '50%',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(59, 130, 246, 0.2) 0%, transparent 70%)',
          filter: 'blur(100px)'
        }} />
        <Box sx={{
          position: 'absolute',
          bottom: '-10%',
          right: '-10%',
          width: '50%',
          height: '50%',
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(45, 212, 191, 0.15) 0%, transparent 70%)',
          filter: 'blur(100px)'
        }} />
      </Box>

      {/* Sidebar Area */}
      {sidebarOpen && (
        <AppSidebar
          isOpen={sidebarOpen}
          onToggle={() => setSidebarOpen(!sidebarOpen)}
          onOpenSettings={() => setSettingsOpen(true)}
          hasApiKey={hasApiKey}
        />
      )}

      {/* Main Content Area */}
      <Box 
        component="main" 
        sx={{ 
          flex: 1, 
          display: 'flex', 
          flexDirection: 'column', 
          height: '100%', 
          position: 'relative',
          zIndex: 1
        }}
      >
        <ChatContainer
          apiKey={apiKey}
          sidebarOpen={sidebarOpen}
          onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        />
      </Box>

      {/* Settings Dialog */}
      <SettingsDialog
        open={settingsOpen}
        onOpenChange={setSettingsOpen}
        apiKey={apiKey}
        onSaveApiKey={setApiKey}
      />
    </Box>
  );
}
