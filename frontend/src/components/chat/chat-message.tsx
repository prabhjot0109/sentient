import { useState } from "react";
import { Box, Chip, Collapse, IconButton, Tooltip, Typography } from "@mui/material";
import {
  Check as CheckIcon,
  ContentCopy as CopyIcon,
  DescriptionOutlined as SourceIcon,
  ExpandMore as ExpandMoreIcon,
} from "@mui/icons-material";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message, RetrievedSource } from "@/types";

interface ChatMessageProps {
  message: Message;
}

// Markdown element styling, scoped to the assistant message body so responses
// read like ChatGPT output (headings, lists, code, tables) instead of raw text.
const markdownSx = {
  color: "text.primary",
  fontSize: "1rem",
  lineHeight: 1.75,
  "& > *:first-of-type": { mt: 0 },
  "& > *:last-child": { mb: 0 },
  "& p": { my: 1.25 },
  "& h1, & h2, & h3, & h4": {
    fontWeight: 650,
    lineHeight: 1.3,
    mt: 2.5,
    mb: 1,
    letterSpacing: "-0.01em",
  },
  "& h1": { fontSize: "1.4rem" },
  "& h2": { fontSize: "1.2rem" },
  "& h3": { fontSize: "1.05rem" },
  "& ul, & ol": { my: 1.25, pl: 3 },
  "& li": { my: 0.4 },
  "& li::marker": { color: "text.secondary" },
  "& a": {
    color: "#7eb6ff",
    textDecoration: "underline",
    textUnderlineOffset: "2px",
  },
  "& strong": { fontWeight: 650 },
  "& blockquote": {
    borderLeft: "3px solid var(--stroke-strong)",
    pl: 2,
    my: 1.5,
    color: "text.secondary",
  },
  "& code": {
    fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
    fontSize: "0.86em",
    backgroundColor: "rgba(255, 255, 255, 0.08)",
    borderRadius: "5px",
    px: "0.4em",
    py: "0.15em",
  },
  "& pre": {
    backgroundColor: "#0d0d0d",
    border: "1px solid var(--stroke-subtle)",
    borderRadius: "12px",
    p: 2,
    my: 1.5,
    overflowX: "auto",
  },
  "& pre code": {
    backgroundColor: "transparent",
    p: 0,
    fontSize: "0.85rem",
    lineHeight: 1.6,
  },
  "& table": {
    borderCollapse: "collapse",
    my: 1.5,
    width: "100%",
    fontSize: "0.9rem",
  },
  "& th, & td": {
    border: "1px solid var(--stroke-subtle)",
    px: 1.25,
    py: 0.75,
    textAlign: "left",
  },
  "& th": { backgroundColor: "rgba(255, 255, 255, 0.04)", fontWeight: 600 },
  "& hr": { border: "none", borderTop: "1px solid var(--stroke-subtle)", my: 2 },
} as const;

export function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (isUser) {
    return (
      <Box sx={{ display: "flex", justifyContent: "flex-end", width: "100%" }}>
        <Box
          sx={{
            maxWidth: "85%",
            borderRadius: "20px",
            backgroundColor: "#303030",
            px: 2,
            py: 1.25,
            color: "text.primary",
            fontSize: "1rem",
            lineHeight: 1.7,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {message.content}
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: "100%",
        // reveal the action row when hovering anywhere over the message
        "&:hover .message-actions": { opacity: 1 },
      }}
    >
      <Box sx={markdownSx}>
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {message.content}
        </ReactMarkdown>
      </Box>

      {message.sources && message.sources.length > 0 && (
        <>
          <SourceTags sources={message.sources} />
          <RetrievedLore sources={message.sources} />
        </>
      )}

      <Box
        className="message-actions"
        sx={{
          mt: 0.5,
          opacity: 0,
          transition: "opacity 140ms ease",
          "@media (hover: none)": { opacity: 1 },
        }}
      >
        <Tooltip title={copied ? "Copied" : "Copy"} placement="bottom">
          <IconButton
            size="small"
            onClick={handleCopy}
            aria-label="Copy response"
            sx={{
              color: copied ? "success.main" : "text.secondary",
              "&:hover": {
                color: "text.primary",
                backgroundColor: "rgba(255, 255, 255, 0.06)",
              },
            }}
          >
            {copied ? (
              <CheckIcon sx={{ fontSize: 16 }} />
            ) : (
              <CopyIcon sx={{ fontSize: 16 }} />
            )}
          </IconButton>
        </Tooltip>
      </Box>
    </Box>
  );
}

// At-a-glance provenance: one chip per distinct source (filename + page) the
// answer was grounded on. The full chunk text lives in the expandable panel below.
function SourceTags({ sources }: { sources: RetrievedSource[] }) {
  const seen = new Set<string>();
  const tags: string[] = [];
  for (const source of sources) {
    const label = `${source.source}${source.page_label ?? ""}`.trim();
    if (label && !seen.has(label)) {
      seen.add(label);
      tags.push(label);
    }
  }

  if (tags.length === 0) {
    return null;
  }

  return (
    <Box sx={{ mt: 1.25, display: "flex", flexWrap: "wrap", gap: 0.75, alignItems: "center" }}>
      <Typography variant="caption" sx={{ color: "text.secondary", mr: 0.25 }}>
        Sources
      </Typography>
      {tags.map((label) => (
        <Chip
          key={label}
          icon={<SourceIcon sx={{ fontSize: 14 }} />}
          label={label}
          size="small"
          sx={{
            height: 24,
            borderRadius: "8px",
            border: "1px solid var(--stroke-subtle)",
            backgroundColor: "rgba(255, 255, 255, 0.03)",
            color: "text.secondary",
            "& .MuiChip-label": { px: 0.75, fontSize: "0.74rem", fontWeight: 500 },
            "& .MuiChip-icon": { color: "text.secondary", ml: 0.5 },
          }}
        />
      ))}
    </Box>
  );
}

// Inspector panel: shows the lore chunks the RAG layer retrieved for this answer,
// so retrieval accuracy is visible when testing without the game connected.
function RetrievedLore({ sources }: { sources: RetrievedSource[] }) {
  const [open, setOpen] = useState(false);

  return (
    <Box sx={{ mt: 1.25 }}>
      <Box
        component="button"
        onClick={() => setOpen((value) => !value)}
        sx={{
          display: "inline-flex",
          alignItems: "center",
          gap: 0.5,
          background: "none",
          border: "none",
          cursor: "pointer",
          p: 0,
          color: "text.secondary",
          fontSize: "0.8rem",
          fontWeight: 500,
          "&:hover": { color: "text.primary" },
        }}
      >
        <ExpandMoreIcon
          sx={{
            fontSize: 18,
            transition: "transform 140ms ease",
            transform: open ? "rotate(180deg)" : "none",
          }}
        />
        Retrieved lore ({sources.length})
      </Box>

      <Collapse in={open}>
        <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 1 }}>
          {sources.map((source, index) => (
            <Box
              key={source.chunk_id ?? index}
              sx={{
                border: "1px solid var(--stroke-subtle)",
                borderRadius: "10px",
                p: 1.25,
                backgroundColor: "rgba(255, 255, 255, 0.02)",
              }}
            >
              <Box
                sx={{
                  display: "flex",
                  justifyContent: "space-between",
                  gap: 1,
                  mb: 0.5,
                }}
              >
                <Typography
                  variant="caption"
                  sx={{ color: "text.secondary", fontWeight: 600 }}
                >
                  {source.source}
                  {source.page_label}
                </Typography>
                {typeof source.score === "number" && (
                  <Tooltip title="Relevance score (higher = closer match)" placement="left">
                    <Typography
                      variant="caption"
                      sx={{
                        color: "text.secondary",
                        fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
                        whiteSpace: "nowrap",
                      }}
                    >
                      ◇ {source.score.toFixed(3)}
                    </Typography>
                  </Tooltip>
                )}
              </Box>
              <Typography
                variant="body2"
                sx={{
                  color: "text.secondary",
                  fontSize: "0.85rem",
                  lineHeight: 1.6,
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                }}
              >
                {source.content}
              </Typography>
            </Box>
          ))}
        </Box>
      </Collapse>
    </Box>
  );
}
