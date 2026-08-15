import { motion, useInView } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { Brain, Database, MessageSquare, Sparkles, User } from "lucide-react";

type Step = {
  key: string;
  icon: React.ReactNode;
  label: string;
  detail: string;
};

const steps: Step[] = [
  {
    key: "q",
    icon: <User className="h-3.5 w-3.5" />,
    label: "Player asks",
    detail: '"Where is the Dragonborn?"',
  },
  {
    key: "r",
    icon: <Database className="h-3.5 w-3.5" />,
    label: "Retrieved",
    detail: "3 lore chunks · Whiterun archives",
  },
  {
    key: "m",
    icon: <Brain className="h-3.5 w-3.5" />,
    label: "Memory",
    detail: "Last spoke 4 in-game days ago",
  },
  {
    key: "t",
    icon: <Sparkles className="h-3.5 w-3.5" />,
    label: "Reasoning",
    detail: "gpt-4o-mini · 214 tokens",
  },
  {
    key: "a",
    icon: <MessageSquare className="h-3.5 w-3.5" />,
    label: "NPC replies",
    detail: "Streaming · 84ms TTFT",
  },
];

const npcLine =
  "Last I heard, the Dragonborn was climbing High Hrothgar to seek the Greybeards. If you hurry, you may find them before nightfall.";

export function HeroConversation() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.3 });
  const [active, setActive] = useState(0);
  const [typed, setTyped] = useState("");

  useEffect(() => {
    if (!inView) return;
    let i = 0;
    const id = setInterval(() => {
      i = (i + 1) % (steps.length + 1);
      setActive(i);
      if (i === steps.length) setTyped("");
    }, 1400);
    return () => clearInterval(id);
  }, [inView]);

  useEffect(() => {
    if (active !== steps.length) return;
    let n = 0;
    const id = setInterval(() => {
      n += 2;
      setTyped(npcLine.slice(0, n));
      if (n >= npcLine.length) clearInterval(id);
    }, 22);
    return () => clearInterval(id);
  }, [active]);

  return (
    <div
      ref={ref}
      className="grid gap-3 rounded-[22px] bg-[oklch(0.09_0.014_265)] p-4 sm:p-6 md:grid-cols-[1.05fr_1fr]"
    >
      {/* Pipeline */}
      <div className="rounded-2xl border border-border/60 bg-white/[0.02] p-5">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs text-muted-foreground">
            <span className="h-2 w-2 rounded-full bg-[oklch(0.7_0.18_150)]" />
            Runtime pipeline
          </div>
          <span className="font-mono text-[10px] tracking-widest text-muted-foreground">
            sentient · skyrim
          </span>
        </div>

        <ol className="relative space-y-3">
          {steps.map((s, i) => {
            const state = active > i ? "done" : active === i ? "active" : "idle";
            return (
              <li key={s.key} className="relative flex items-start gap-3">
                <div
                  className={`mt-0.5 flex h-6 w-6 flex-none items-center justify-center rounded-full border transition-all duration-500 ${
                    state === "idle"
                      ? "border-border/70 text-muted-foreground"
                      : "border-[oklch(0.86_0.14_220_/_0.7)] text-foreground"
                  }`}
                  style={{
                    background:
                      state === "active"
                        ? "oklch(1 0 0 / 0.06)"
                        : state === "done"
                          ? "oklch(1 0 0 / 0.06)"
                          : "transparent",
                    boxShadow: state === "active" ? "0 0 0 4px oklch(1 0 0 / 0.06)" : "none",
                  }}
                >
                  {s.icon}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="text-sm font-medium">{s.label}</span>
                    <span className="font-mono text-[10px] text-muted-foreground">
                      0.{20 + i * 12}s
                    </span>
                  </div>
                  <p className="truncate text-xs text-muted-foreground">{s.detail}</p>
                  <div className="mt-2 h-px w-full overflow-hidden rounded bg-white/5">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: state === "idle" ? 0 : "100%" }}
                      transition={{ duration: 0.7, ease: "easeOut" }}
                      className="h-full"
                      style={{ background: "var(--brand)" }}
                    />
                  </div>
                </div>
              </li>
            );
          })}
        </ol>
      </div>

      {/* Chat */}
      <div className="flex flex-col rounded-2xl border border-border/60 bg-white/[0.02] p-5">
        <div className="mb-4 flex items-center gap-2 text-xs text-muted-foreground">
          <div className="flex gap-1">
            <span className="h-2 w-2 rounded-full bg-white/20" />
            <span className="h-2 w-2 rounded-full bg-white/20" />
            <span className="h-2 w-2 rounded-full bg-white/20" />
          </div>
          <span className="ml-2 font-mono text-[10px] tracking-widest">whiterun · guard #14</span>
        </div>

        <div className="flex flex-1 flex-col justify-end gap-3">
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="ml-auto max-w-[85%] rounded-2xl rounded-br-md bg-white/[0.06] px-4 py-2.5 text-sm"
          >
            Where is the Dragonborn?
          </motion.div>

          {active >= steps.length - 1 && (
            <motion.div
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              className="mr-auto max-w-[92%] rounded-2xl rounded-bl-md border border-border/60 bg-white/[0.04] px-4 py-3 text-sm leading-relaxed"
            >
              <div className="mb-1 flex items-center gap-2 text-[10px] uppercase tracking-widest text-muted-foreground">
                <span
                  className="h-1.5 w-1.5 rounded-full"
                  style={{ background: "var(--cyan-glow)" }}
                />
                Guard · Whiterun
              </div>
              <p>
                {typed}
                <span className="animate-caret ml-0.5 inline-block h-3.5 w-[2px] translate-y-[2px] bg-foreground" />
              </p>
            </motion.div>
          )}
        </div>

        <div className="mt-4 flex items-center gap-2 rounded-full border border-border/60 bg-black/40 px-3 py-2">
          <MessageSquare className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-xs text-muted-foreground">Speak to the guard…</span>
          <span className="ml-auto font-mono text-[10px] text-muted-foreground">⌘K</span>
        </div>
      </div>
    </div>
  );
}
