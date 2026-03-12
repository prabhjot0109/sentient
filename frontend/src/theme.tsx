import { alpha, createTheme } from "@mui/material/styles";

export const theme = createTheme({
  palette: {
    mode: "dark",
    primary: {
      main: "#f4f4f5",
      light: "#ffffff",
      dark: "#d4d4d8",
      contrastText: "#09090b",
    },
    background: {
      default: "#212121",
      paper: "#171717",
    },
    text: {
      primary: "#ececec",
      secondary: "#a1a1aa",
    },
    divider: "rgba(255, 255, 255, 0.1)",
    error: {
      main: "#f87171",
    },
    success: {
      main: "#4ade80",
    },
  },
  spacing: 8,
  shape: {
    borderRadius: 8,
  },
  typography: {
    fontFamily:
      '"Geist Sans", "Geist", "Inter", "Segoe UI Variable", "Segoe UI", sans-serif',
    h1: {
      fontWeight: 700,
      letterSpacing: "-0.05em",
    },
    h2: {
      fontWeight: 700,
      letterSpacing: "-0.04em",
    },
    h3: {
      fontWeight: 700,
      letterSpacing: "-0.03em",
    },
    h4: {
      fontWeight: 650,
      letterSpacing: "-0.02em",
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
          backgroundColor: "rgba(255, 255, 255, 0.22)",
          color: "#09090b",
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
          backgroundColor: "#f4f4f5",
          color: "#09090b",
          "&:hover": {
            backgroundColor: "#e4e4e7",
          },
        },
        outlined: {
          borderColor: "rgba(255, 255, 255, 0.12)",
          "&:hover": {
            borderColor: "rgba(255, 255, 255, 0.2)",
            backgroundColor: "rgba(255, 255, 255, 0.04)",
          },
        },
        text: {
          "&:hover": {
            backgroundColor: "rgba(255, 255, 255, 0.04)",
          },
        },
      },
    },
    MuiPaper: {
      styleOverrides: {
        root: {
          backgroundImage: "none",
          backgroundColor: "#171717",
          border: "1px solid rgba(255, 255, 255, 0.1)",
          boxShadow: "none",
        },
      },
    },
    MuiDrawer: {
      styleOverrides: {
        paper: {
          backgroundColor: "#171717",
          borderRight: "1px solid rgba(255, 255, 255, 0.1)",
        },
      },
    },
    MuiDialog: {
      styleOverrides: {
        paper: {
          borderRadius: 12,
          backgroundColor: "#171717",
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
              borderColor: "rgba(255, 255, 255, 0.12)",
            },
            "&:hover": {
              backgroundColor: "rgba(255, 255, 255, 0.03)",
            },
            "&:hover fieldset": {
              borderColor: "rgba(255, 255, 255, 0.18)",
            },
            "&.Mui-focused": {
              backgroundColor: alpha("#ffffff", 0.03),
            },
            "&.Mui-focused fieldset": {
              borderColor: "#f4f4f5",
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
