import { createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#3b82f6", // Core blue
      light: "#60a5fa",
      dark: "#2563eb",
    },
    background: {
      default: "#09090b", // Deep black
      paper: "#121215", // Surface/Card
    },
    text: {
      primary: "#fafafa",
      secondary: "#a1a1aa",
    },
    divider: "rgba(255, 255, 255, 0.05)",
  },
  typography: {
    fontFamily: '"Inter", "Outfit", sans-serif',
    h1: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 700,
    },
    h2: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 700,
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
    },
  },
  shape: {
    borderRadius: 16,
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          padding: "8px 20px",
        },
        containedPrimary: {
          background: "linear-gradient(135deg, #3b82f6 0%, #2dd4bf 100%)",
          boxShadow: "0 4px 14px 0 rgba(59, 130, 246, 0.39)",
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          border: "1px solid rgba(255, 255, 255, 0.05)",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: "#0c0c0e",
          borderRight: "1px solid rgba(255, 255, 255, 0.05)",
        },
      },
    },
  },
});
