import { formatFileSize } from "@/lib/utils";
import {
  Box,
  IconButton,
  ListItem,
  ListItemText,
  Typography,
} from "@mui/material";
import {
  ArticleOutlined as TxtIcon,
  DeleteOutline as DeleteIcon,
  DescriptionOutlined as FileIcon,
  InsertDriveFileOutlined as CodeIcon,
} from "@mui/icons-material";
import type { Source } from "@/types";

interface SourceItemProps {
  source: Source;
  onDelete: () => void;
}

export function SourceItem({ source, onDelete }: SourceItemProps) {
  const isPdf = source.name.toLowerCase().endsWith(".pdf");
  const isTxt = source.name.toLowerCase().endsWith(".txt");
  const Icon = isPdf ? FileIcon : isTxt ? TxtIcon : CodeIcon;

  return (
    <ListItem
      disablePadding
      sx={{
        borderRadius: "8px",
        backgroundColor: "transparent",
        border: "1px solid transparent",
        transition: "background-color 160ms ease, border-color 160ms ease",
        overflow: "hidden",
        width: "100%",
        minWidth: 0,
        "&:hover": {
          backgroundColor: "rgba(255, 255, 255, 0.04)",
          borderColor: "rgba(255, 255, 255, 0.08)",
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
          sx={{
            color: "text.secondary",
            mr: 0.5,
            "&:hover": { color: "error.main" },
          }}
        >
          <DeleteIcon fontSize="inherit" sx={{ fontSize: 16 }} />
        </IconButton>
      }
    >
      <Box
        sx={{
          display: "flex",
          alignItems: "center",
          gap: 1.25,
          p: 1,
          width: "100%",
          justifyContent: "flex-start",
        }}
      >
        <Box
          sx={{
            width: 32,
            height: 32,
            display: "grid",
            placeItems: "center",
            borderRadius: "6px",
            bgcolor: "rgba(255, 255, 255, 0.03)",
            flexShrink: 0,
          }}
        >
          <Icon sx={{ color: "text.secondary", fontSize: 18 }} />
        </Box>
        <ListItemText
          primary={
            <Typography
              variant="body2"
              noWrap
              sx={{
                fontWeight: 500,
                fontSize: "0.85rem",
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
                fontSize: "0.72rem",
              }}
            >
              {formatFileSize(source.size)}
            </Typography>
          }
          sx={{ m: 0 }}
        />
      </Box>
    </ListItem>
  );
}
