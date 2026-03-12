import { formatFileSize } from "@/lib/utils";
import {
  Box,
  IconButton,
  ListItem,
  ListItemText,
  Tooltip,
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
  isCollapsed?: boolean;
}

export function SourceItem({ source, onDelete, isCollapsed }: SourceItemProps) {
  const isPdf = source.name.toLowerCase().endsWith(".pdf");
  const isTxt = source.name.toLowerCase().endsWith(".txt");
  const Icon = isPdf ? FileIcon : isTxt ? TxtIcon : CodeIcon;

  const content = (
    <ListItem
      disablePadding
      sx={{
        borderRadius: 2,
        backgroundColor: "transparent",
        border: "1px solid transparent",
        transition: "background-color 160ms ease, border-color 160ms ease",
        overflow: "hidden",
        width: isCollapsed ? 40 : "100%",
        minWidth: isCollapsed ? 40 : 0,
        "&:hover": {
          backgroundColor: "rgba(255, 255, 255, 0.04)",
          borderColor: "rgba(255, 255, 255, 0.08)",
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
            sx={{
              color: "text.secondary",
              mr: 0.5,
              "&:hover": { color: "error.main" },
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
          gap: isCollapsed ? 0 : 1,
          p: isCollapsed ? 0.75 : 1,
          width: "100%",
          justifyContent: isCollapsed ? "center" : "flex-start",
        }}
      >
        <Box
          sx={{
            width: 32,
            height: 32,
            display: "grid",
            placeItems: "center",
            borderRadius: 2,
            bgcolor: "rgba(255, 255, 255, 0.02)",
            flexShrink: 0,
          }}
        >
          <Icon sx={{ color: "text.secondary", fontSize: 18 }} />
        </Box>
        {!isCollapsed && (
          <ListItemText
            primary={
              <Typography
                variant="body2"
                noWrap
                sx={{
                  fontWeight: 500,
                  fontSize: "0.84rem",
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
        )}
      </Box>
    </ListItem>
  );

  if (isCollapsed) {
    return (
      <Tooltip title={source.name} placement="right">
        {content}
      </Tooltip>
    );
  }

  return content;
}
