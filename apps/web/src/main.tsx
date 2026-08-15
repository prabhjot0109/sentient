import { StrictMode, Suspense, lazy } from "react";
import { createRoot } from "react-dom/client";
import { Box, CircularProgress, Typography } from "@mui/material";
import { ThemeProvider } from "@mui/material/styles";
import CssBaseline from "@mui/material/CssBaseline";
import { theme } from "./theme";
import "./index.css";

const App = lazy(() => import("./App"));

function LoadingFallback() {
  return (
    <Box
      sx={{
        minHeight: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        px: 3,
      }}
    >
      <Box sx={{ display: "grid", justifyItems: "center", gap: 2.5 }}>
        <CircularProgress size={32} thickness={4} />
        <Typography variant="body2" sx={{ color: "text.secondary" }}>
          Loading workspace
        </Typography>
      </Box>
    </Box>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <Suspense fallback={<LoadingFallback />}>
        <App />
      </Suspense>
    </ThemeProvider>
  </StrictMode>
);
