import { motion, AnimatePresence } from "framer-motion";
import { useState } from "react";
import { SectionHeader } from "./SectionHeader";

import imgMultiproject from "@/assets/features/multiproject.webp";
import imgMemory from "@/assets/features/memory.webp";
import imgConfigurable from "@/assets/features/configurable.webp";
import imgKnowledge from "@/assets/features/knowledge.webp";
import imgRetrieval from "@/assets/features/retrieval.webp";
import imgStreaming from "@/assets/features/streaming.webp";
import imgOpenai from "@/assets/features/openai.webp";
import imgAsync from "@/assets/features/async.webp";

type Feature = {
  id: string;
  title: string;
  desc: string;
  image: string;
  accent: string;
  accentFg: string;
};

const features: Feature[] = [
  {
    id: "multiproject",
    title: "Multi-project",
    desc: "Isolated worlds — separate prompts, RAG, and models per game.",
    image: imgMultiproject,
    accent: "oklch(0.28 0.06 280)",
    accentFg: "oklch(0.68 0.11 45)",
  },
  {
    id: "memory",
    title: "Memory",
    desc: "Long-term recall and conversation summaries. NPCs remember you.",
    image: imgMemory,
    accent: "oklch(0.26 0.07 295)",
    accentFg: "oklch(0.68 0.11 45)",
  },
  {
    id: "configurable",
    title: "Configurable AI",
    desc: "OpenAI, Gemini, Groq, OpenRouter — any compatible endpoint.",
    image: imgConfigurable,
    accent: "oklch(0.26 0.05 220)",
    accentFg: "oklch(0.68 0.11 45)",
  },
  {
    id: "knowledge",
    title: "Upload knowledge",
    desc: "PDF, TXT, lore books, manuals — chunked and indexed automatically.",
    image: imgKnowledge,
    accent: "oklch(0.26 0.05 75)",
    accentFg: "oklch(0.68 0.11 45)",
  },
  {
    id: "retrieval",
    title: "Fast retrieval",
    desc: "Configurable chunking, similarity search, embedding selection.",
    image: imgRetrieval,
    accent: "oklch(0.25 0.04 190)",
    accentFg: "oklch(0.68 0.11 45)",
  },
  {
    id: "streaming",
    title: "Streaming",
    desc: "Low latency, fast time-to-first-token. Feels alive.",
    image: imgStreaming,
    accent: "oklch(0.24 0.06 150)",
    accentFg: "oklch(0.68 0.11 45)",
  },
  {
    id: "openai",
    title: "OpenAI compatible",
    desc: "Drop-in replacement for Mantella and any OpenAI client.",
    image: imgOpenai,
    accent: "oklch(0.24 0.04 220)",
    accentFg: "oklch(0.68 0.11 45)",
  },
  {
    id: "async",
    title: "Async runtime",
    desc: "Background indexing, concurrent requests, no cold conversations.",
    image: imgAsync,
    accent: "oklch(0.26 0.06 30)",
    accentFg: "oklch(0.68 0.11 45)",
  },
];

const ease = [0.22, 1, 0.36, 1] as const;

export function Features() {
  const [activeId, setActiveId] = useState<string | null>(null);

  const activeFeature = features.find((f) => f.id === activeId);

  return (
    <section id="platform" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <SectionHeader
          eyebrow="Platform features"
          title={<>Every primitive an intelligent NPC needs.</>}
          description="A composable runtime, tuned for real games and real players."
        />

        <div className="relative mt-20">
          {/* Feature list */}
          <motion.ul
            initial="hidden"
            whileInView="show"
            viewport={{ once: true, amount: 0.1 }}
            variants={{
              hidden: {},
              show: {
                transition: { staggerChildren: 0.05, delayChildren: 0.1 },
              },
            }}
            className="relative"
          >
            {/* Top border */}
            <div
              className="h-px w-full"
              style={{
                background: "oklch(1 0 0 / 0.1)",
              }}
            />

            {features.map((f) => {
              const isActive = activeId === f.id;
              return (
                <motion.li
                  key={f.id}
                  variants={{
                    hidden: { opacity: 0, y: 10 },
                    show: {
                      opacity: 1,
                      y: 0,
                      transition: { duration: 0.5, ease },
                    },
                  }}
                  onMouseEnter={() => setActiveId(f.id)}
                  onMouseLeave={() => setActiveId(null)}
                  onClick={() => setActiveId(isActive ? null : f.id)}
                  className="group relative cursor-pointer sm:cursor-default"
                  style={{
                    backgroundColor: isActive ? f.accent : "transparent",
                    transition: "background-color 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
                  }}
                >
                  {/* Active left edge indicator */}
                  <div
                    className="absolute inset-y-0 left-0 w-[3px]"
                    style={{
                      backgroundColor: isActive ? f.accentFg : "transparent",
                      transition: "background-color 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
                    }}
                  />

                  <div className="px-6 py-5 sm:px-8 sm:py-6">
                    <div className="flex items-center justify-between">
                      {/* Title */}
                      <h3
                        className="text-lg font-semibold uppercase tracking-[0.04em] sm:text-xl md:text-2xl"
                        style={{
                          color: isActive ? f.accentFg : "oklch(0.85 0 0)",
                          transition:
                            "color 0.35s cubic-bezier(0.22, 1, 0.36, 1), letter-spacing 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
                          letterSpacing: isActive ? "0.06em" : "0.04em",
                        }}
                      >
                        {f.title}
                      </h3>

                      <span className="text-[11px] font-mono text-muted-foreground opacity-60 lg:hidden">
                        {isActive ? "Collapse" : "View"}
                      </span>
                    </div>

                    {/* Description */}
                    <p
                      className="mt-1 text-sm sm:text-[15px]"
                      style={{
                        color: isActive ? "oklch(0.95 0 0 / 0.85)" : "oklch(0.65 0 0)",
                        transition: "color 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
                      }}
                    >
                      {f.desc}
                    </p>

                    {/* Inline mobile expandable image preview */}
                    <AnimatePresence>
                      {isActive && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: "auto" }}
                          exit={{ opacity: 0, height: 0 }}
                          className="mt-4 overflow-hidden rounded-xl lg:hidden border border-white/10"
                        >
                          <img
                            src={f.image}
                            alt={f.title}
                            className="w-full aspect-[16/9] object-cover"
                          />
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>

                  {/* Bottom divider */}
                  <div
                    className="h-px w-full"
                    style={{
                      background: isActive
                        ? f.accentFg.replace(")", " / 0.35)")
                        : "oklch(1 0 0 / 0.1)",
                      transition: "background 0.35s cubic-bezier(0.22, 1, 0.36, 1)",
                    }}
                  />
                </motion.li>
              );
            })}
          </motion.ul>

          {/* Desktop Preview: Hover-driven floating preview */}
          <AnimatePresence mode="wait">
            {activeFeature && (
              <motion.div
                key={activeFeature.id}
                initial={{ opacity: 0, x: 24 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 24 }}
                transition={{ duration: 0.3, ease }}
                className="pointer-events-none fixed right-6 top-1/2 z-40 hidden -translate-y-1/2 lg:right-12 lg:block xl:right-20"
              >
                <div
                  className="relative w-80 overflow-hidden rounded-xl lg:w-lg xl:w-160"
                  style={{
                    aspectRatio: "3 / 2",
                    boxShadow: `0 24px 64px -16px oklch(0 0 0 / 0.85), 0 0 0 1px ${activeFeature.accentFg.replace(")", " / 0.2)")}`,
                  }}
                >
                  <img
                    src={activeFeature.image}
                    alt={activeFeature.title}
                    width={1536}
                    height={1024}
                    className="h-full w-full object-cover"
                  />
                  {/* Subtle bottom vignette */}
                  <div
                    className="absolute inset-x-0 bottom-0 h-1/3"
                    style={{
                      background: "oklch(0.06 0.01 260 / 0.45)",
                    }}
                  />
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>
    </section>
  );
}
