import { alpha, createTheme } from "@mui/material/styles";

const surfaceRaised = "#171717";
const strokeSubtle = "rgba(255, 255, 255, 0.08)";
const strokeStrong = "rgba(255, 255, 255, 0.15)";
const accentWhite = "#ffffff";
const accentWhiteHover = "#e2e2e7";
const inkOnWhite = "#000000";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: accentWhite,
      light: accentWhiteHover,
      dark: "#cccccc",
      contrastText: inkOnWhite,
    },
    background: {
      default: "#0d0d0d",
      paper: surfaceRaised,
    },
    text: {
      primary: "#ececec",
      secondary: "#b4b4b4",
    },
    divider: strokeSubtle,
    error: {
      main: "#ef4444",
    },
    success: {
      main: "#22c55e",
    },
  },
  spacing: 8,
  shape: {
    borderRadius: 8,
  },
  typography: {
    fontFamily:
      '"IBM Plex Sans", "Segoe UI Variable", "Segoe UI", sans-serif',
    h1: {
      fontFamily: '"IBM Plex Sans", "Segoe UI Variable", "Segoe UI", sans-serif',
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    h2: {
      fontFamily: '"IBM Plex Sans", "Segoe UI Variable", "Segoe UI", sans-serif',
      fontWeight: 700,
      letterSpacing: "-0.02em",
    },
    h3: {
      fontFamily: '"IBM Plex Sans", "Segoe UI Variable", "Segoe UI", sans-serif',
      fontWeight: 600,
      letterSpacing: "-0.01em",
    },
    h4: {
      fontFamily: '"IBM Plex Sans", "Segoe UI Variable", "Segoe UI", sans-serif',
      fontWeight: 600,
      letterSpacing: "-0.01em",
    },
    h5: {
      fontWeight: 650,
      letterSpacing: "-0.02em",
    },
    h6: {
      fontWeight: 650,
      letterSpacing: "-0.015em",
    },
    subtitle1: {
      fontWeight: 600,
    },
    subtitle2: {
      fontWeight: 600,
    },
    body1: {
      lineHeight: 1.7,
    },
    body2: {
      lineHeight: 1.65,
    },
    button: {
      textTransform: "none",
      fontWeight: 600,
      letterSpacing: "-0.01em",
    },
    overline: {
      fontWeight: 700,
      letterSpacing: "0.1em",
      textTransform: "uppercase",
    },
  },
  components: {
    MuiCssBaseline: {
      styleOverrides: {
        "::selection": {
          backgroundColor: "rgba(255, 255, 255, 0.16)",
          color: "#ffffff",
        },
      },
    },
    MuiButton: {
      defaultProps: {
        disableElevation: true,
      },
      styleOverrides: {
        root: {
          borderRadius: 8,
          minHeight: 38,
          paddingInline: 14,
          transition:
            "background-color 160ms ease, border-color 160ms ease, color 160ms ease",
        },
        containedPrimary: {
          backgroundColor: accentWhite,
          color: inkOnWhite,
          "&:hover": {
            backgroundColor: accentWhiteHover,
          },
        },
        outlined: {
          borderColor: strokeStrong,
          "&:hover": {
            borderColor: accentWhite,
            backgroundColor: "rgba(255, 255, 255, 0.06)",
          },
        },
        text: {
          "&:hover": {
            backgroundColor: "rgba(255, 255, 255, 0.06)",
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: surfaceRaised,
          border: `1px solid ${strokeSubtle}`,
          boxShadow: "none",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: surfaceRaised,
          borderRight: `1px solid ${strokeSubtle}`,
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 12,
          backgroundColor: surfaceRaised,
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: 8,
            backgroundColor: "rgba(255, 255, 255, 0.02)",
            transition: "border-color 160ms ease, background-color 160ms ease",
            "& fieldset": {
              borderColor: strokeStrong,
            },
            "&:hover": {
              backgroundColor: "rgba(255, 255, 255, 0.04)",
            },
            "&:hover fieldset": {
              borderColor: accentWhite,
            },
            "&.Mui-focused": {
              backgroundColor: alpha(accentWhite, 0.04),
            },
            "&.Mui-focused fieldset": {
              borderColor: accentWhite,
            },
          },
        },
      },
    },
    MuiAlert: {
      styleOverrides: {
        root: {
          borderRadius: 8,
        },
      },
    },
  },
});
