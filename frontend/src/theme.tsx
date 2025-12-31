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
    grey: {
      100: "#f4f4f5",
      200: "#e4e4e7",
      300: "#d4d4d8",
      400: "#a1a1aa",
      500: "#71717a",
      600: "#52525b",
      700: "#3f3f46",
      800: "#27272a",
      900: "#18181b",
    },
    text: {
      primary: "#fafafa",
      secondary: "#a1a1aa",
    },
    divider: "rgba(255, 255, 255, 0.06)",
  },
  typography: {
    fontFamily: '"Inter", "Outfit", sans-serif',
    h1: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    h2: {
      fontFamily: '"Outfit", sans-serif',
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
      letterSpacing: "0.01em",
    },
  },
  shape: {
    borderRadius: 20, // More curvy
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          borderRadius: 12,
          padding: "10px 24px",
          transition: "all 0.2s ease-in-out",
          "&:hover": {
            transform: "translateY(-1px)",
          },
        },
        containedPrimary: {
          background: "linear-gradient(135deg, #3b82f6 0%, #2dd4bf 100%)",
          boxShadow: "0 4px 20px 0 rgba(59, 130, 246, 0.2)",
          "&:hover": {
            boxShadow: "0 6px 24px 0 rgba(59, 130, 246, 0.3)",
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: "#121215",
          border: "1px solid rgba(255, 255, 255, 0.05)",
          boxShadow: "0 8px 32px 0 rgba(0, 0, 0, 0.4)",
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
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: 16,
            backgroundColor: "rgba(255, 255, 255, 0.03)",
            transition: "all 0.2s ease-in-out",
            "& fieldset": {
              borderColor: "rgba(255, 255, 255, 0.08)",
            },
            "&:hover fieldset": {
              borderColor: "rgba(255, 255, 255, 0.15)",
            },
            "&.Mui-focused fieldset": {
              borderColor: "#3b82f6",
              borderWidth: "1px",
            },
          },
        },
      },
    },
  },
});
