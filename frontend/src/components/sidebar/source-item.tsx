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
}

export function SourceItem({ source, onDelete }: SourceItemProps) {
  const isPdf = source.name.toLowerCase().endsWith(".pdf");
  const isTxt = source.name.toLowerCase().endsWith(".txt");

  return (
    <ListItem
      disablePadding
      sx={{
        mb: 1,
        borderRadius: 2,
        backgroundColor: "rgba(255, 255, 255, 0.02)",
        border: "1px solid rgba(255, 255, 255, 0.05)",
        transition: "all 0.2s",
        "&:hover": {
          backgroundColor: "rgba(255, 255, 255, 0.05)",
          borderColor: "rgba(59, 130, 246, 0.2)",
          "& .delete-btn": { opacity: 1 },
        },
      }}
      secondaryAction={
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
          }}
        >
          <DeleteIcon fontSize="small" />
        </IconButton>
      }
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          p: 1.5,
          width: "100%",
          cursor: "pointer",
        }}
      >
        <ListItemIcon sx={{ minWidth: 40 }}>
          {isPdf ? (
            <FileIcon sx={{ color: "#ef4444" }} />
          ) : isTxt ? (
            <TxtIcon sx={{ color: "#3b82f6" }} />
          ) : (
            <CodeIcon sx={{ color: "#a1a1aa" }} />
          )}
        </ListItemIcon>
        <ListItemText
          primary={
            <Typography variant="body2" sx={{ fontWeight: 600, noWrap: true }}>
              {source.name}
            </Typography>
          }
          secondary={
            <Typography
              variant="caption"
              sx={{ color: "text.secondary", display: "block" }}
            >
              {formatFileSize(source.size)} • {isPdf ? "PDF" : "Text"}
            </Typography>
          }
          sx={{ mr: 4 }}
        />
      </Box>
    </ListItem>
  );
}
