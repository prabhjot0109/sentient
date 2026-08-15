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
    color: "#ffffff",
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
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    borderRadius: "5px",
    px: "0.4em",
    py: "0.15em",
    color: "#ffffff",
  },
  "& pre": {
    backgroundColor: "var(--surface-inset)",
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
      <Box
        sx={{
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-end",
          width: "100%",
          mb: 1,
          "&:hover .message-actions": { opacity: 1 },
        }}
      >
        <Box
          sx={{
            maxWidth: "75%",
            borderRadius: "20px",
            backgroundColor: "rgba(255, 255, 255, 0.06)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            px: 2.5,
            py: 1.25,
            color: "#ffffff",
            fontSize: "0.975rem",
            lineHeight: 1.6,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
          }}
        >
          {message.content}
        </Box>

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
              aria-label="Copy message"
              sx={{
                color: copied ? "success.main" : "text.secondary",
                "&:hover": {
                  color: "#ffffff",
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                },
              }}
            >
              {copied ? (
                <CheckIcon sx={{ fontSize: 14 }} />
              ) : (
                <CopyIcon sx={{ fontSize: 14 }} />
              )}
            </IconButton>
          </Tooltip>
        </Box>
      </Box>
    );
  }

  return (
    <Box
      sx={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        gap: 1.25,
        mb: 2.5,
        "&:hover .message-actions": { opacity: 1 },
      }}
    >
      {/* Assistant Header Row */}
      <Box sx={{ display: "flex", alignItems: "center", gap: 1.25, mt: 1 }}>
        <Box
          sx={{
            width: 24,
            height: 24,
            borderRadius: "50%",
            backgroundColor: "#ffffff",
            color: "#000000",
            display: "grid",
            placeItems: "center",
            fontWeight: 700,
            fontSize: "0.75rem",
          }}
        >
          S
        </Box>
        <Typography
          variant="subtitle2"
          sx={{
            color: "#ffffff",
            fontWeight: 650,
            fontSize: "0.9rem",
          }}
        >
          Sentient
        </Typography>
      </Box>

      {/* Message Content */}
      <Box sx={{ pl: 0, pr: { md: 4 } }}>
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
            mt: 1,
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
                  color: "#ffffff",
                  backgroundColor: "rgba(255, 255, 255, 0.06)",
                },
              }}
            >
              {copied ? (
                <CheckIcon sx={{ fontSize: 14 }} />
              ) : (
                <CopyIcon sx={{ fontSize: 14 }} />
              )}
            </IconButton>
          </Tooltip>
        </Box>
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
    <Box sx={{ mt: 1.5, display: "flex", flexWrap: "wrap", gap: 0.75, alignItems: "center" }}>
      <Typography variant="caption" sx={{ color: "text.secondary", mr: 0.25 }}>
        Sources
      </Typography>
      {tags.map((label) => (
        <Chip
          key={label}
          icon={<SourceIcon sx={{ fontSize: 13 }} />}
          label={label}
          size="small"
          sx={{
            height: 24,
            borderRadius: "6px",
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
    <Box sx={{ mt: 1.5 }}>
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
          fontFamily: "var(--font-display)",
          fontSize: "0.75rem",
          fontWeight: 600,
          letterSpacing: "0.06em",
          textTransform: "uppercase",
          "&:hover": { color: "#ffffff" },
        }}
      >
        <ExpandMoreIcon
          sx={{
            fontSize: 16,
            transition: "transform 140ms ease",
            transform: open ? "rotate(180deg)" : "none",
          }}
        />
        Lore Entries ({sources.length})
      </Box>

      <Collapse in={open}>
        <Box sx={{ mt: 1, display: "flex", flexDirection: "column", gap: 1 }}>
          {sources.map((source, index) => {
            const relevancePct =
              typeof source.score === "number"
                ? Math.round(Math.max(0, Math.min(1, source.score)) * 100)
                : null;

            return (
              <Box
                key={source.chunk_id ?? index}
                sx={{
                  borderLeft: "2px solid var(--accent-amber)",
                  borderRadius: "4px",
                  p: 1.25,
                  backgroundColor: "var(--surface-inset)",
                }}
              >
                <Box
                  sx={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    gap: 1,
                    mb: 0.5,
                  }}
                >
                  <Typography
                    variant="caption"
                    sx={{
                      fontFamily: "var(--font-display)",
                      color: "text.secondary",
                      fontWeight: 600,
                      letterSpacing: "0.02em",
                    }}
                  >
                    {source.source}
                    {source.page_label}
                  </Typography>
                  {relevancePct !== null && (
                    <Tooltip title="Relevance score (higher = closer match)" placement="left">
                      <Box sx={{ display: "flex", alignItems: "center", gap: 0.75 }}>
                        <Box
                          sx={{
                            width: 40,
                            height: 4,
                            borderRadius: "999px",
                            backgroundColor: "rgba(255, 255, 255, 0.08)",
                            overflow: "hidden",
                          }}
                        >
                          <Box
                            sx={{
                              width: `${relevancePct}%`,
                              height: "100%",
                              backgroundColor: "var(--accent-amber)",
                            }}
                          />
                        </Box>
                        <Typography
                          variant="caption"
                          sx={{
                            color: "text.secondary",
                            fontFamily: '"IBM Plex Mono", ui-monospace, monospace',
                            whiteSpace: "nowrap",
                          }}
                        >
                          {source.score!.toFixed(3)}
                        </Typography>
                      </Box>
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
            );
          })}
        </Box>
      </Collapse>
    </Box>
  );
}
