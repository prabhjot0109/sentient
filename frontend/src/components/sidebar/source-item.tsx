import { formatFileSize } from "@/lib/utils";
import {
  ListItem,
  ListItemIcon,
  ListItemText,
  IconButton,
  Typography,
  Box,
  Tooltip,
} from "@mui/material";
import {
  Description as FileIcon,
  DeleteOutline as DeleteIcon,
  Code as CodeIcon,
  Article as TxtIcon,
} from "@mui/icons-material";
import type { Source } from "@/types";

interface SourceItemProps {
  source: Source;
  onDelete: () => void;
  isCollapsed?: boolean;
}

export function SourceItem({ source, onDelete, isCollapsed }: SourceItemProps) {
  const isPdf = source.name.toLowerCase().endsWith(".pdf");
  const isTxt = source.name.toLowerCase().endsWith(".txt");

  const Content = (
    <ListItem
      disablePadding
      sx={{
        borderRadius: 4,
        backgroundColor: "rgba(255, 255, 255, 0.03)",
        border: "1px solid rgba(255, 255, 255, 0.05)",
        transition: "all 0.2s cubic-bezier(0.4, 0, 0.2, 1)",
        overflow: "hidden",
        width: isCollapsed ? 48 : "100%",
        minWidth: isCollapsed ? 48 : 0,
        "&:hover": {
          backgroundColor: "rgba(255, 255, 255, 0.06)",
          borderColor: "rgba(59, 130, 246, 0.2)",
          transform: "scale(1.02)",
          "& .delete-btn": { opacity: 1 },
        },
      }}
      secondaryAction={
        !isCollapsed && (
          <IconButton
            edge="end"
            aria-label="delete"
            onClick={(e) => {
              e.stopPropagation();
              onDelete();
            }}
            className="delete-btn"
            sx={{
              opacity: 0,
              transition: "opacity 0.2s",
              color: "error.main",
              "&:hover": { backgroundColor: "rgba(239, 68, 68, 0.1)" },
              mr: 0.5,
            }}
          >
            <DeleteIcon fontSize="inherit" sx={{ fontSize: 16 }} />
          </IconButton>
        )
      }
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          p: isCollapsed ? 1 : 1.5,
          width: "100%",
          cursor: "pointer",
          justifyContent: isCollapsed ? "center" : "flex-start",
        }}
      >
        <ListItemIcon
          sx={{ minWidth: isCollapsed ? 0 : 40, justifyContent: "center" }}
        >
          {isPdf ? (
            <FileIcon sx={{ color: "#ef4444", fontSize: 20 }} />
          ) : isTxt ? (
            <TxtIcon sx={{ color: "#3b82f6", fontSize: 20 }} />
          ) : (
            <CodeIcon sx={{ color: "#a1a1aa", fontSize: 20 }} />
          )}
        </ListItemIcon>
        {!isCollapsed && (
          <ListItemText
            primary={
              <Typography
                variant="body2"
                noWrap
                sx={{
                  fontWeight: 700,
                  fontSize: "0.8rem",
                  color: "text.primary",
                }}
              >
                {source.name}
              </Typography>
            }
            secondary={
              <Typography
                variant="caption"
                sx={{
                  color: "text.secondary",
                  display: "block",
                  fontSize: "0.65rem",
                  opacity: 0.6,
                }}
              >
                {formatFileSize(source.size)}
              </Typography>
            }
            sx={{ m: 0 }}
          />
        )}
      </Box>
    </ListItem>
  );

  if (isCollapsed) {
    return (
      <Tooltip title={source.name} placement="right">
        {Content}
      </Tooltip>
    );
  }

  return Content;
}
