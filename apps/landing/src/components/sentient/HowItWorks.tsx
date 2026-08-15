import { motion, useScroll, useTransform } from "framer-motion";
import { useRef, useState } from "react";
import { SectionHeader } from "./SectionHeader";
import {
  BookOpen,
  Gamepad2,
  MessagesSquare,
  Rocket,
  Settings2,
  ArrowRight,
  Terminal,
} from "lucide-react";

const ease = [0.22, 1, 0.36, 1] as const;

const steps = [
  {
    id: "create",
    icon: Gamepad2,
    kicker: "01 · Initialize",
    title: "Create a game",
    detail:
      "Spin up a project for your world. Define personas, factions, scenes — the canonical spine of every conversation.",
    code: [
      { p: "$ ", c: "text-foreground/40" },
      { p: "sentient ", c: "text-foreground/90" },
      { p: "games create ", c: "text-foreground/70" },
      { p: "skyrim", c: "text-[oklch(0.82_0.12_150)]" },
    ],
    meta: "project.yaml · 1 world · 0 npcs",
  },
  {
    id: "lore",
    icon: BookOpen,
    kicker: "02 · Ingest",
    title: "Upload lore & docs",
    detail:
      "Push PDFs, wikis, quest books, transcripts. Sentient chunks, embeds, and indexes — grounding every response in canon.",
    code: [
      { p: "$ ", c: "text-foreground/40" },
      { p: "sentient ", c: "text-foreground/90" },
      { p: "docs push ", c: "text-foreground/70" },
      { p: "./lore ", c: "text-[oklch(0.82_0.12_150)]" },
      { p: "--recursive", c: "text-[oklch(0.7_0.02_260)]" },
    ],
    meta: "1,284 chunks · 12.4 MB · indexed",
  },
  {
    id: "config",
    icon: Settings2,
    kicker: "03 · Configure",
    title: "Configure AI & embeddings",
    detail:
      "Pick a language model, an embedding model, a retrieval strategy, and memory windows. Preview responses inline.",
    code: [
      { p: "model:      ", c: "text-foreground/50" },
      { p: "gpt-4o-mini\n", c: "text-[oklch(0.85_0.14_220)]" },
      { p: "embed:      ", c: "text-foreground/50" },
      { p: "text-embed-3-large\n", c: "text-[oklch(0.85_0.14_220)]" },
      { p: "retriever:  ", c: "text-foreground/50" },
      { p: "hybrid", c: "text-[oklch(0.88_0.09_80)]" },
    ],
    meta: "temperature 0.7 · memory 8k",
  },
  {
    id: "test",
    icon: MessagesSquare,
    kicker: "04 · Rehearse",
    title: "Talk & test in the UI",
    detail:
      "Chat with any NPC in the studio. Inspect retrieved context, trace token spans, tune persona voice live.",
    code: [
      { p: "> ", c: "text-foreground/40" },
      { p: '"Where is the Dragonborn?"\n', c: "text-[oklch(0.82_0.12_150)]" },
      { p: "guard_14: ", c: "text-foreground/50" },
      { p: '"Last seen near Whiterun gates…"', c: "text-foreground/90" },
    ],
    meta: "trace · 312ms · 4 chunks recalled",
  },
  {
    id: "deploy",
    icon: Rocket,
    kicker: "05 · Ship",
    title: "Deploy & use",
    detail:
      "Point Mantella, your engine plugin, or any OpenAI-compatible client at your endpoint. Live in production.",
    code: [
      { p: "baseURL: ", c: "text-foreground/50" },
      { p: "https://api.sentient.dev/v1\n", c: "text-[oklch(0.85_0.14_220)]" },
      { p: "apiKey:  ", c: "text-foreground/50" },
      { p: "sk-sentient-••••", c: "text-[oklch(0.88_0.09_80)]" },
    ],
    meta: "region: iad · p50 240ms",
  },
];

export function HowItWorks() {
  const wrapRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: wrapRef,
    offset: ["start 70%", "end 30%"],
  });
  const lineScale = useTransform(scrollYProgress, [0, 1], [0, 1]);

  const [active, setActive] = useState<string | null>(null);

  return (
    <section id="how" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <SectionHeader
          eyebrow="How it works"
          title={
            <>
              Five steps from empty project
              <br />
              to a world that talks back.
            </>
          }
          description="A workflow designed for developers who ship. No glue code, no brittle prompt chains — just a clear path from idea to live NPCs."
        />

        <div ref={wrapRef} className="relative mt-24">
          {/* Rail */}
          <div
            aria-hidden
            className="absolute left-5 top-0 h-full w-px sm:left-1/2 sm:-translate-x-1/2"
            style={{
              background: "oklch(1 0 0 / 0.08)",
            }}
          />
          <motion.div
            aria-hidden
            style={{ scaleY: lineScale, transformOrigin: "top" }}
            className="absolute left-5 top-0 h-full w-px sm:left-1/2 sm:-translate-x-1/2"
          >
            <div
              className="h-full w-full"
              style={{
                background: "oklch(0.68 0.11 45 / 0.55)",
                boxShadow: "0 0 24px oklch(0.68 0.11 45 / 0.35)",
              }}
            />
          </motion.div>

          <ol className="space-y-16 sm:space-y-24">
            {steps.map((s, i) => {
              const right = i % 2 === 1;
              const Icon = s.icon;
              const isActive = active === s.id;
              return (
                <motion.li
                  key={s.id}
                  initial={{ opacity: 0, y: 28 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.35 }}
                  transition={{ duration: 0.8, ease }}
                  onHoverStart={() => setActive(s.id)}
                  onHoverEnd={() => setActive(null)}
                  className="relative grid grid-cols-[40px_1fr] gap-6 sm:grid-cols-2 sm:gap-16"
                >
                  {/* Node */}
                  <div className="relative row-span-2 sm:col-span-2 sm:row-auto">
                    <div className="absolute left-5 top-3 -translate-x-1/2 sm:left-1/2">
                      <motion.div
                        animate={{
                          scale: isActive ? 1.15 : 1,
                        }}
                        transition={{ duration: 0.4, ease }}
                        className="relative flex h-9 w-9 items-center justify-center rounded-full"
                        style={{
                          background: "oklch(0.11 0.004 260)",
                          border: "1px solid oklch(1 0 0 / 0.12)",
                          boxShadow:
                            "0 0 0 6px oklch(0.055 0.004 260), 0 10px 30px -8px oklch(0.68 0.11 45 / 0.45), inset 0 1px 0 oklch(1 0 0 / 0.08)",
                        }}
                      >
                        <Icon className="h-4 w-4 text-foreground/85" />
                        {isActive && (
                          <motion.span
                            layoutId="pulse-ring"
                            className="absolute inset-0 rounded-full"
                            style={{
                              boxShadow:
                                "0 0 0 1px oklch(0.68 0.11 45 / 0.5), 0 0 40px oklch(0.68 0.11 45 / 0.55)",
                            }}
                          />
                        )}
                      </motion.div>
                    </div>
                  </div>

                  {/* Text block */}
                  <div
                    className={`${
                      right
                        ? "sm:col-start-2 sm:row-start-1 sm:pl-10"
                        : "sm:col-start-1 sm:row-start-1 sm:pr-10 sm:text-right"
                    } col-start-2`}
                  >
                    <div
                      className={`flex items-center gap-2 font-mono text-[10px] uppercase tracking-[0.28em] text-foreground/40 ${
                        right ? "" : "sm:justify-end"
                      }`}
                    >
                      <span className="h-px w-6 bg-foreground/20" />
                      {s.kicker}
                    </div>
                    <h3 className="mt-3 font-display text-[clamp(1.5rem,2.4vw,2rem)] font-semibold leading-[1.05] tracking-[-0.025em] text-foreground">
                      {s.title}
                    </h3>
                    <p
                      className={`mt-3 max-w-md text-[15px] leading-[1.65] text-foreground/60 ${
                        right ? "" : "sm:ml-auto"
                      }`}
                    >
                      {s.detail}
                    </p>
                  </div>

                  {/* Code card */}
                  <div
                    className={`${
                      right
                        ? "sm:col-start-1 sm:row-start-1 sm:pr-10"
                        : "sm:col-start-2 sm:row-start-1 sm:pl-10"
                    } col-start-2`}
                  >
                    <motion.div
                      whileHover={{ y: -3 }}
                      transition={{ duration: 0.4, ease }}
                      className="glass group relative overflow-hidden rounded-2xl"
                    >
                      {/* header */}
                      <div className="flex items-center justify-between border-b border-white/[0.06] px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <Terminal className="h-3 w-3 text-foreground/40" />
                          <span className="font-mono text-[10px] uppercase tracking-[0.22em] text-foreground/40">
                            {s.id}.sh
                          </span>
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="h-1.5 w-1.5 rounded-full bg-[oklch(0.82_0.12_150)]" />
                          <span className="font-mono text-[10px] text-foreground/40">ready</span>
                        </div>
                      </div>

                      {/* code */}
                      <pre className="overflow-x-auto px-4 py-4 font-mono text-[12.5px] leading-[1.7] text-left">
                        <code>
                          {s.code.map((seg, k) => (
                            <span key={k} className={seg.c}>
                              {seg.p}
                            </span>
                          ))}
                        </code>
                      </pre>

                      {/* meta */}
                      <div className="flex items-center justify-between border-t border-white/[0.06] px-4 py-2.5">
                        <span className="font-mono text-[10.5px] text-foreground/40">{s.meta}</span>
                        <ArrowRight className="h-3 w-3 text-foreground/30 transition-transform duration-500 group-hover:translate-x-0.5 group-hover:text-foreground/70" />
                      </div>

                      {/* shimmer on hover */}
                      <motion.div
                        aria-hidden
                        initial={false}
                        animate={{ opacity: isActive ? 1 : 0 }}
                        transition={{ duration: 0.6 }}
                        className="pointer-events-none absolute inset-0 rounded-2xl"
                        style={{
                          background: "oklch(0.68 0.11 45 / 0.05)",
                        }}
                      />
                    </motion.div>
                  </div>
                </motion.li>
              );
            })}
          </ol>
        </div>
      </div>
    </section>
  );
}
