import { motion } from "framer-motion";
import { useState } from "react";
import type { LucideIcon } from "lucide-react";
import { SectionHeader } from "./SectionHeader";
import {
  Brain,
  Cpu,
  FileText,
  Gem,
  MessageSquare,
  Mountain,
  Radiation,
  Sparkles,
  Swords,
  Wand2,
} from "lucide-react";

type GamePanel = {
  label: string;
  value: string;
  fill: number;
};

type Game = {
  id: string;
  name: string;
  status: "Live" | "Beta" | "Roadmap";
  icon: LucideIcon;
  tagline: string;
  panels: GamePanel[];
  npcs: string[];
  files: [string, string][];
};

const games: Game[] = [
  {
    id: "skyrim",
    name: "Skyrim",
    status: "Live",
    icon: Mountain,
    tagline: "Nordic realm",
    panels: [
      { label: "Chats", value: "2,481", fill: 78 },
      { label: "Documents", value: "312", fill: 52 },
      { label: "Prompts", value: "48", fill: 38 },
      { label: "Memory", value: "18.4k", fill: 84 },
    ],
    npcs: ["Guard #14", "Lydia", "Belethor", "Balgruuf", "Farengar", "Adrianne"],
    files: [
      ["lore/skyrim-provinces.pdf", "1.2 MB"],
      ["quests/main.md", "42 KB"],
      ["wiki/factions.json", "318 KB"],
    ],
  },
  {
    id: "fallout",
    name: "Fallout 4",
    status: "Live",
    icon: Radiation,
    tagline: "Wasteland",
    panels: [
      { label: "Chats", value: "1,842", fill: 68 },
      { label: "Documents", value: "245", fill: 42 },
      { label: "Prompts", value: "32", fill: 28 },
      { label: "Memory", value: "12.1k", fill: 64 },
    ],
    npcs: [
      "Codsworth",
      "Piper Wright",
      "Nick Valentine",
      "Paladin Danse",
      "Preston Garvey",
      "Deacon",
    ],
    files: [
      ["vault-tec/manual.pdf", "850 KB"],
      ["wasteland/settlements.json", "112 KB"],
      ["factions/brotherhood.md", "28 KB"],
    ],
  },
  {
    id: "cyberpunk",
    name: "Cyberpunk",
    status: "Roadmap",
    icon: Cpu,
    tagline: "Night City",
    panels: [
      { label: "Chats", value: "4,102", fill: 92 },
      { label: "Documents", value: "512", fill: 78 },
      { label: "Prompts", value: "64", fill: 58 },
      { label: "Memory", value: "28.6k", fill: 95 },
    ],
    npcs: [
      "Johnny Silverhand",
      "Jackie Welles",
      "Judy Alvarez",
      "Panam Palmer",
      "Rogue",
      "Takemura",
    ],
    files: [
      ["netwatch/daemons.bin", "2.4 MB"],
      ["arasaka/hierarchy.pdf", "540 KB"],
      ["nc-history/districts.md", "94 KB"],
    ],
  },
  {
    id: "elden",
    name: "Elden Ring",
    status: "Roadmap",
    icon: Swords,
    tagline: "Lands Between",
    panels: [
      { label: "Chats", value: "954", fill: 45 },
      { label: "Documents", value: "128", fill: 31 },
      { label: "Prompts", value: "16", fill: 18 },
      { label: "Memory", value: "6.2k", fill: 42 },
    ],
    npcs: ["Melina", "Ranni the Witch", "Blaidd", "Alexander", "Patches", "Gideon Ofnir"],
    files: [
      ["lore/shattered-ring.pdf", "1.6 MB"],
      ["lands-between/grace.json", "74 KB"],
      ["demigods/runes.md", "18 KB"],
    ],
  },
  {
    id: "custom",
    name: "Custom world",
    status: "Live",
    icon: Wand2,
    tagline: "Your IP",
    panels: [
      { label: "Chats", value: "124", fill: 15 },
      { label: "Documents", value: "15", fill: 10 },
      { label: "Prompts", value: "8", fill: 8 },
      { label: "Memory", value: "1.1k", fill: 12 },
    ],
    npcs: ["Custom Companion", "Questgiver AI", "Merchant NPC"],
    files: [
      ["my-world/lore-book.txt", "12 KB"],
      ["my-world/system-prompt.md", "8 KB"],
    ],
  },
];

const ease = [0.22, 1, 0.36, 1] as const;

function getPanelIcon(label: string) {
  switch (label) {
    case "Chats":
      return <MessageSquare className="h-3.5 w-3.5" />;
    case "Documents":
      return <FileText className="h-3.5 w-3.5" />;
    case "Prompts":
      return <Sparkles className="h-3.5 w-3.5" />;
    case "Memory":
      return <Brain className="h-3.5 w-3.5" />;
    default:
      return <Gem className="h-3.5 w-3.5" />;
  }
}

export function Games() {
  const [active, setActive] = useState("skyrim");
  const current = games.find((g) => g.id === active)!;

  return (
    <section id="games" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-5xl px-6">
        <SectionHeader
          eyebrow="Multi-game platform"
          title={
            <>
              One platform. <span className="text-brand">Every world.</span>
            </>
          }
          description="Every game is its own project — independent lore, prompts, memory, and models. Switch worlds like tabs."
        />

        <motion.div
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.9, ease }}
          className="mt-16 grid gap-6 lg:grid-cols-[300px_1fr]"
        >
          {/* Projects rail */}
          <div className="glass h-fit overflow-hidden rounded-3xl p-3 lg:sticky lg:top-24">
            <div className="flex items-center justify-between px-3 pb-3 pt-2">
              <span className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground">
                Projects
              </span>
              <span className="rounded-full border border-border/60 px-1.5 font-mono text-[10px] text-muted-foreground/70">
                {games.length}
              </span>
            </div>
            <motion.ul
              initial="hidden"
              whileInView="show"
              viewport={{ once: true, amount: 0.3 }}
              variants={{
                hidden: {},
                show: { transition: { staggerChildren: 0.06, delayChildren: 0.1 } },
              }}
              className="space-y-1"
            >
              {games.map((g) => {
                const on = g.id === active;
                const Icon = g.icon;
                return (
                  <motion.li
                    key={g.id}
                    variants={{
                      hidden: { opacity: 0, x: -8 },
                      show: { opacity: 1, x: 0, transition: { duration: 0.5, ease } },
                    }}
                  >
                    <button
                      onClick={() => setActive(g.id)}
                      onMouseEnter={() => setActive(g.id)}
                      className="group relative flex w-full items-center gap-3 overflow-hidden rounded-xl px-3 py-2.5 text-left text-sm transition-colors duration-300 hover:bg-white/[0.035]"
                    >
                      {on && (
                        <motion.span
                          layoutId="games-active"
                          transition={{ type: "spring", stiffness: 420, damping: 36 }}
                          aria-hidden
                          className="absolute inset-0 -z-10 rounded-xl border border-white/[0.08] bg-white/[0.06]"
                        />
                      )}
                      <span
                        className={`flex h-9 w-9 flex-none items-center justify-center rounded-lg border transition-colors duration-300 ${
                          on
                            ? "border-brand/30 bg-brand/15 text-brand"
                            : "border-white/[0.06] bg-white/[0.03] text-muted-foreground group-hover:text-foreground"
                        }`}
                      >
                        <Icon className="h-4 w-4" strokeWidth={1.6} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate font-medium leading-tight">{g.name}</span>
                        <span className="block truncate text-[11px] text-muted-foreground/70">
                          {g.tagline}
                        </span>
                      </span>
                      <span
                        className={`flex flex-none items-center gap-1 rounded-full border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-[0.12em] ${
                          g.status === "Live"
                            ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-400"
                            : g.status === "Beta"
                              ? "border-amber-500/25 bg-amber-500/10 text-amber-400"
                              : "border-border/60 bg-white/[0.02] text-muted-foreground"
                        }`}
                      >
                        <span
                          aria-hidden
                          className={`h-1 w-1 rounded-full ${
                            g.status === "Live"
                              ? "bg-emerald-400"
                              : g.status === "Beta"
                                ? "bg-amber-400"
                                : "bg-muted-foreground/60"
                          }`}
                        />
                        {g.status}
                      </span>
                    </button>
                  </motion.li>
                );
              })}
            </motion.ul>
          </div>

          {/* Runtime detail */}
          <motion.div
            key={current.id}
            initial={{ opacity: 0, y: 16, filter: "blur(8px)" }}
            animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
            transition={{ duration: 0.55, ease }}
            className="glass-strong relative overflow-hidden rounded-3xl p-6"
          >
            <div
              aria-hidden
              className="absolute inset-0 -z-10 bg-gradient-to-br from-brand/10 via-transparent to-transparent opacity-60 pointer-events-none"
            />

            <div className="flex items-center justify-between">
              <div>
                <div className="font-mono text-[10px] uppercase tracking-[0.24em] text-muted-foreground">
                  Project / {current.name}
                </div>
                <h3 className="mt-1.5 text-2xl font-semibold tracking-tight">
                  {current.name}
                  <span className="text-muted-foreground/50"> · runtime</span>
                </h3>
              </div>

              <span className="flex items-center gap-2 rounded-full border border-border/60 bg-black/40 px-3 py-1 font-mono text-[10px] text-muted-foreground">
                <span className="relative flex h-1.5 w-1.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-60" />
                  <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-emerald-400" />
                </span>
                api.sentient.dev/v1
              </span>
            </div>

            <motion.div
              initial="hidden"
              animate="show"
              variants={{
                hidden: {},
                show: { transition: { staggerChildren: 0.05, delayChildren: 0.1 } },
              }}
              className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4"
            >
              {current.panels.map((p) => (
                <motion.div
                  key={p.label}
                  variants={{
                    hidden: { opacity: 0, y: 10 },
                    show: { opacity: 1, y: 0, transition: { duration: 0.5, ease } },
                  }}
                  whileHover={{ y: -2 }}
                  className="glass group/panel rounded-2xl p-4 transition-colors duration-300 hover:border-white/[0.12]"
                >
                  <div className="flex items-center gap-2 text-xs text-muted-foreground">
                    <span className="transition-colors duration-300 group-hover/panel:text-foreground">
                      {getPanelIcon(p.label)}
                    </span>
                    {p.label}
                  </div>
                  <div className="mt-2 text-2xl font-semibold tracking-tight tabular-nums">
                    {p.value}
                  </div>
                  <div className="mt-3 h-[3px] w-full overflow-hidden rounded-full bg-white/[0.05]">
                    <motion.div
                      initial={{ width: 0 }}
                      whileInView={{ width: `${p.fill}%` }}
                      viewport={{ once: true }}
                      transition={{ duration: 1.1, ease, delay: 0.15 }}
                      className="h-full rounded-full bg-brand"
                    />
                  </div>
                </motion.div>
              ))}
            </motion.div>

            <div className="mt-4 grid gap-3 sm:grid-cols-[1fr_1fr]">
              <div className="glass rounded-2xl p-4">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <span>Active NPCs</span>
                  <span className="font-mono text-[10px] text-muted-foreground/60">
                    {current.npcs.length} online
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {current.npcs.map((n, i) => (
                    <motion.span
                      key={n}
                      initial={{ opacity: 0, y: 6 }}
                      whileInView={{ opacity: 1, y: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.4, ease, delay: 0.04 * i }}
                      whileHover={{ y: -1 }}
                      className="cursor-default rounded-full border border-border/60 bg-white/[0.03] px-2.5 py-1 text-xs transition-colors duration-300 hover:border-white/20 hover:bg-white/[0.06]"
                    >
                      {n}
                    </motion.span>
                  ))}
                </div>
              </div>
              <div className="glass rounded-2xl p-4">
                <div className="text-xs text-muted-foreground">Retrieval sources</div>
                <ul className="mt-3 space-y-1.5 font-mono text-xs">
                  {current.files.map(([f, s], i) => (
                    <motion.li
                      key={f}
                      initial={{ opacity: 0, x: -6 }}
                      whileInView={{ opacity: 1, x: 0 }}
                      viewport={{ once: true }}
                      transition={{ duration: 0.4, ease, delay: 0.06 * i }}
                      className="group/row flex cursor-default justify-between rounded-md px-1.5 py-0.5 transition-colors duration-300 hover:bg-white/[0.04]"
                    >
                      <span className="text-foreground/80 transition-colors group-hover/row:text-foreground">
                        {f}
                      </span>
                      <span className="text-muted-foreground">{s}</span>
                    </motion.li>
                  ))}
                </ul>
              </div>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
