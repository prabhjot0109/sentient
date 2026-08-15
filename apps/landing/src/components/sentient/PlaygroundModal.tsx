import { motion, AnimatePresence } from "framer-motion";
import { useState, useEffect, useRef } from "react";
import {
  X,
  Send,
  Sparkles,
  Database,
  Brain,
  Cpu,
  Volume2,
  Terminal,
  RefreshCw,
  Layers,
  CheckCircle2,
  Mountain,
  Radiation,
  Swords,
} from "lucide-react";
import { usePlayground } from "./PlaygroundContext";

type CharacterConfig = {
  id: string;
  game: string;
  gameIcon: React.ReactNode;
  name: string;
  role: string;
  avatarAccent: string;
  greeting: string;
  systemModel: string;
  defaultLore: string[];
  suggestedPrompts: { q: string; a: string; lore: string; memory: string }[];
};

const CHARACTERS: CharacterConfig[] = [
  {
    id: "skyrim-guard",
    game: "Skyrim",
    gameIcon: <Mountain className="h-3.5 w-3.5" />,
    name: "Guard Valerius",
    role: "Whiterun City Garrison",
    avatarAccent: "oklch(0.68 0.11 45)",
    greeting: "Hold, traveler. State your business in Whiterun, or move along.",
    systemModel: "sentient-gpt4o-rag",
    defaultLore: [
      "Whiterun City Guard Ledger: Caius commands the garrison.",
      "Hold Decree: Dragons reported near Bleak Falls Barrow.",
      "Player status: Thane of Whiterun, honored by Jarl Balgruuf.",
    ],
    suggestedPrompts: [
      {
        q: "Any word on dragon sightings near Whiterun?",
        a: "Aye. Jarl Balgruuf sent scouts toward Bleak Falls yesterday. Keep your sword sharp and your eyes on the peaks.",
        lore: "Whiterun Scouts Report #441",
        memory: "Dragonborn recognized (+50 affinity)",
      },
      {
        q: "Who commands the hold's defenses?",
        a: "Commander Caius leads our men from the guardhouse. If you need bounties, see the steward Proventus inside Dragonsreach.",
        lore: "Garrison Command Roster",
        memory: "First question regarding military structure",
      },
      {
        q: "I used to be an adventurer like you...",
        a: "Then you took an arrow to the knee, aye? We have all heard the tale. Still, if your sword arm works, Whiterun can use you.",
        lore: "Nordic Common Dialect Vol. II",
        memory: "Humor interaction acknowledged",
      },
    ],
  },
  {
    id: "fallout-nick",
    game: "Fallout 4",
    gameIcon: <Radiation className="h-3.5 w-3.5" />,
    name: "Nick Valentine",
    role: "Private Investigator · Diamond City",
    avatarAccent: "oklch(0.72 0.14 75)",
    greeting: "Valentine Detective Agency. If it's missing, stolen, or suspicious, I'm listening.",
    systemModel: "sentient-claude-synthetics",
    defaultLore: [
      "Detective Casefile #902: Institute synth rumors in Diamond City.",
      "Memory Core: Pre-war police instincts layered on prototype synth chassis.",
      "Player status: General of the Minutemen.",
    ],
    suggestedPrompts: [
      {
        q: "What's the latest on Institute synth infiltrations?",
        a: "Mayor McDonough says there are no synths in Diamond City, but between you and me, people don't vanish into thin air without a trace.",
        lore: "Casefile: Missing Residents of Fenway",
        memory: "Shared suspicion of Institute",
      },
      {
        q: "How's business at the detective agency?",
        a: "Always a fresh case in the Commonwealth. Lost caravans, runaway spouses, and plenty of folks who think their neighbors aren't human.",
        lore: "Agency Caseload Manifest",
        memory: "Detective partnership established",
      },
      {
        q: "Do you ever think about your pre-war memories?",
        a: "Every day, pal. Having two men's memories inside one tin head is an acquired taste, but it keeps the gears turning.",
        lore: "Valentine Prototype Diagnostics",
        memory: "Deep persona background recalled",
      },
    ],
  },
  {
    id: "cyberpunk-johnny",
    game: "Cyberpunk",
    gameIcon: <Cpu className="h-3.5 w-3.5" />,
    name: "Johnny Silverhand",
    role: "Rockerboy · Relic Engram",
    avatarAccent: "oklch(0.7 0.18 25)",
    greeting: "Wake up, samurai. We got a city to burn.",
    systemModel: "sentient-hybrid-llama3",
    defaultLore: [
      "Relic Biomark: Engram integrity 91.4%.",
      "Arasaka Tower Incident 2023: Soulkiller extraction file.",
      "Player status: Mercenary V, operating in Night City.",
    ],
    suggestedPrompts: [
      {
        q: "What do you think of Arasaka's new security grid?",
        a: "Same old corpo parasites hiding behind thicker ICE. Arasaka thinks they own Night City, but all it takes is one spark to light the fuse.",
        lore: "Netwatch Threat Assessment: Arasaka Subnet",
        memory: "Anti-corpo resonance maxed (+95)",
      },
      {
        q: "Where should we hit next, Johnny?",
        a: "Anywhere it hurts the suits. Mikoshi is the endgame, V. Don't let the neon lights distract you from why we're here.",
        lore: "Relic Synaptic Link Data",
        memory: "V and Johnny shared objective",
      },
    ],
  },
  {
    id: "elden-melina",
    game: "Elden Ring",
    gameIcon: <Swords className="h-3.5 w-3.5" />,
    name: "Melina",
    role: "Kindling Maiden · Lands Between",
    avatarAccent: "oklch(0.78 0.12 150)",
    greeting: "Greetings, traveler from beyond the fog. I offer you an accord.",
    systemModel: "sentient-deepseek-lore",
    defaultLore: [
      "Guidance of Grace: Lost runes restored at Sites of Grace.",
      "The Erdtree: Shattered ring shards scattered across the demigods.",
      "Player status: Tarnished seeker of the Elden Ring.",
    ],
    suggestedPrompts: [
      {
        q: "Tell me about the Erdtree and the Golden Order.",
        a: "The Golden Order is broken, yet the Erdtree still beckons. Turn runes into strength, and take the throne as Elden Lord.",
        lore: "Fragments of the Shattered Ring",
        memory: "Grace pact active",
      },
      {
        q: "Who was Queen Marika?",
        a: "Queen Marika the Eternal... vessel of the Elden Ring. In her sorrow and ambition, the world was sundered.",
        lore: "Leyndell Royal Epistles",
        memory: "Lore inquiry: Demigod lineage",
      },
    ],
  },
];

type Message = {
  id: string;
  sender: "user" | "npc";
  text: string;
  loreSnippet?: string;
  memorySnippet?: string;
  latencyMs?: number;
};

export function PlaygroundModal() {
  const { isOpen, activeCharacterId, closePlayground, openPlayground } = usePlayground();
  const [character, setCharacter] = useState<CharacterConfig>(CHARACTERS[0]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [inputValue, setInputValue] = useState("");
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState("");
  const [activeLoreChunk, setActiveLoreChunk] = useState<string>("");
  const [activeMemory, setActiveMemory] = useState<string>("");
  const [lastLatency, setLastLatency] = useState<number>(84);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Sync active character from context or initial
  useEffect(() => {
    const found = CHARACTERS.find((c) => c.id === activeCharacterId) || CHARACTERS[0];
    setCharacter(found);
    setMessages([
      {
        id: "msg-initial",
        sender: "npc",
        text: found.greeting,
        loreSnippet: found.defaultLore[0],
        memorySnippet: "Character initialized from cold state",
        latencyMs: 38,
      },
    ]);
    setActiveLoreChunk(found.defaultLore[0]);
    setActiveMemory("Memory index: 8,000 tokens context loaded");
  }, [activeCharacterId]);

  // Escape key handler
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        closePlayground();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, closePlayground]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 150);
    }
  }, [isOpen]);

  // Auto-scroll chat
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamedText]);

  const handleSend = (textToSend?: string) => {
    const query = (textToSend || inputValue).trim();
    if (!query || isStreaming) return;

    setInputValue("");
    const userMsg: Message = {
      id: `usr-${Date.now()}`,
      sender: "user",
      text: query,
    };
    setMessages((prev) => [...prev, userMsg]);

    // Find pre-matched answer or generate realistic response
    const matchedPrompt = character.suggestedPrompts.find(
      (p) => p.q.toLowerCase() === query.toLowerCase(),
    );

    const targetAnswer =
      matchedPrompt?.a ||
      `By the authority of ${character.game}, I acknowledge your words: "${query}". Our runtime vectors recall this topic with high confidence.`;

    const targetLore =
      matchedPrompt?.lore ||
      `${character.game} Archives: Vector Match [Similarity: 0.938] for "${query.slice(0, 24)}..."`;

    const targetMemory =
      matchedPrompt?.memory || `Recorded into persistent episodic memory (window 8.2k)`;

    const randomLatency = Math.floor(Math.random() * 35) + 65;
    setLastLatency(randomLatency);
    setActiveLoreChunk(targetLore);
    setActiveMemory(targetMemory);

    setIsStreaming(true);
    setStreamedText("");

    // Simulate streaming tokens
    let charIndex = 0;
    const interval = setInterval(() => {
      charIndex += 3;
      setStreamedText(targetAnswer.slice(0, charIndex));

      if (charIndex >= targetAnswer.length) {
        clearInterval(interval);
        setStreamedText("");
        setIsStreaming(false);
        setMessages((prev) => [
          ...prev,
          {
            id: `npc-${Date.now()}`,
            sender: "npc",
            text: targetAnswer,
            loreSnippet: targetLore,
            memorySnippet: targetMemory,
            latencyMs: randomLatency,
          },
        ]);
      }
    }, 20);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={closePlayground}
          className="fixed inset-0 bg-black/80 backdrop-blur-md"
        />

        {/* Modal Container */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 20 }}
          transition={{ duration: 0.3, ease: [0.22, 1, 0.36, 1] }}
          className="relative w-full max-w-5xl rounded-2xl border border-white/15 bg-background shadow-2xl overflow-hidden z-10 flex flex-col max-h-[90vh]"
          style={{
            boxShadow: "0 30px 100px -20px oklch(0 0 0 / 0.9), 0 0 0 1px oklch(1 0 0 / 0.1)",
          }}
        >
          {/* Header */}
          <div className="flex items-center justify-between border-b border-white/10 bg-white/[0.02] px-5 py-3.5">
            <div className="flex items-center gap-3">
              <div className="flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/5 text-foreground">
                <Sparkles className="h-3.5 w-3.5 text-brand" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <span className="font-display text-sm font-semibold text-foreground">
                    Sentient Runtime Playground
                  </span>
                  <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.2 font-mono text-[9px] uppercase tracking-wider text-emerald-400">
                    Live Stream
                  </span>
                </div>
                <div className="font-mono text-[10px] text-muted-foreground">
                  OpenAI-Compatible Streaming WebSocket API · TTFT {lastLatency}ms
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => {
                  setMessages([
                    {
                      id: "msg-reset",
                      sender: "npc",
                      text: character.greeting,
                      loreSnippet: character.defaultLore[0],
                      memorySnippet: "Memory state refreshed",
                      latencyMs: 35,
                    },
                  ]);
                }}
                className="flex h-8 items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 text-xs text-muted-foreground transition-colors hover:border-white/20 hover:text-foreground"
                title="Clear conversation and reset memory"
              >
                <RefreshCw className="h-3 w-3" />
                <span className="hidden sm:inline font-mono text-[10px]">Reset</span>
              </button>

              <button
                onClick={closePlayground}
                className="flex h-8 w-8 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03] text-muted-foreground transition-colors hover:border-white/20 hover:text-foreground"
                aria-label="Close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Character World Switcher */}
          <div className="flex items-center gap-2 overflow-x-auto border-b border-white/10 bg-black/40 px-5 py-2">
            <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground shrink-0">
              World:
            </span>
            <div className="flex items-center gap-1.5">
              {CHARACTERS.map((c) => {
                const isSelected = c.id === character.id;
                return (
                  <button
                    key={c.id}
                    onClick={() => openPlayground(c.id)}
                    className={`flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all ${
                      isSelected
                        ? "border border-white/20 bg-white/10 text-foreground shadow-sm"
                        : "border border-transparent text-muted-foreground hover:bg-white/[0.04] hover:text-foreground"
                    }`}
                  >
                    {c.gameIcon}
                    <span>{c.name}</span>
                    <span className="font-mono text-[9px] opacity-60">({c.game})</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Main Content Grid: Chat + Telemetry Inspector */}
          <div className="grid flex-1 grid-cols-1 md:grid-cols-12 overflow-hidden">
            {/* Chat Column */}
            <div className="flex flex-col md:col-span-8 border-r border-white/10 bg-background/50 h-[480px] sm:h-[540px]">
              {/* Message Feed */}
              <div className="flex-1 overflow-y-auto p-4 sm:p-5 space-y-4">
                {messages.map((m) => (
                  <motion.div
                    key={m.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className={`flex ${m.sender === "user" ? "justify-end" : "justify-start"}`}
                  >
                    <div
                      className={`max-w-[85%] rounded-2xl p-3.5 text-sm ${
                        m.sender === "user"
                          ? "rounded-br-md bg-white/[0.08] text-foreground border border-white/10"
                          : "rounded-bl-md bg-white/[0.03] text-foreground border border-white/[0.08]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-3 mb-1">
                        <div className="flex items-center gap-1.5">
                          <span
                            className="h-1.5 w-1.5 rounded-full"
                            style={{
                              backgroundColor:
                                m.sender === "user" ? "oklch(0.9 0 0)" : character.avatarAccent,
                            }}
                          />
                          <span className="text-[10px] font-mono uppercase tracking-wider text-muted-foreground">
                            {m.sender === "user" ? "You (Player)" : character.name}
                          </span>
                        </div>
                        {m.latencyMs && (
                          <span className="font-mono text-[9px] text-muted-foreground/60">
                            {m.latencyMs}ms
                          </span>
                        )}
                      </div>
                      <p className="leading-relaxed whitespace-pre-wrap">{m.text}</p>
                    </div>
                  </motion.div>
                ))}

                {/* Streaming Response Bubble */}
                {isStreaming && (
                  <motion.div
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    className="flex justify-start"
                  >
                    <div className="max-w-[85%] rounded-2xl rounded-bl-md bg-white/[0.03] p-3.5 text-sm text-foreground border border-brand/30">
                      <div className="flex items-center gap-2 mb-1 text-[10px] font-mono uppercase tracking-wider text-brand">
                        <span className="h-1.5 w-1.5 rounded-full bg-brand animate-ping" />
                        <span>Streaming ({lastLatency}ms TTFT)...</span>
                      </div>
                      <p className="leading-relaxed">
                        {streamedText}
                        <span className="animate-caret inline-block h-3.5 w-[2px] translate-y-[2px] bg-foreground ml-0.5" />
                      </p>
                    </div>
                  </motion.div>
                )}
                <div ref={chatEndRef} />
              </div>

              {/* Quick Suggestion Chips */}
              <div className="border-t border-white/[0.06] bg-black/20 p-2.5">
                <div className="flex items-center gap-1.5 overflow-x-auto pb-1 text-xs">
                  <span className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-wider shrink-0 mr-1">
                    Try:
                  </span>
                  {character.suggestedPrompts.map((sp, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleSend(sp.q)}
                      disabled={isStreaming}
                      className="shrink-0 rounded-full border border-white/10 bg-white/[0.02] px-2.5 py-1 text-[11px] text-foreground/80 transition-colors hover:border-brand/40 hover:bg-brand/10 hover:text-foreground disabled:opacity-40"
                    >
                      "{sp.q}"
                    </button>
                  ))}
                </div>

                {/* Input Bar */}
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    handleSend();
                  }}
                  className="mt-2 flex items-center gap-2"
                >
                  <input
                    ref={inputRef}
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder={`Speak to ${character.name}...`}
                    disabled={isStreaming}
                    className="flex-1 rounded-xl border border-white/10 bg-white/[0.04] px-3.5 py-2 text-sm text-foreground placeholder:text-muted-foreground/50 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
                  />
                  <button
                    type="submit"
                    disabled={!inputValue.trim() || isStreaming}
                    className="btn-primary shrink-0 h-9 px-4 disabled:opacity-40 disabled:pointer-events-none"
                  >
                    <Send className="h-3.5 w-3.5" />
                    <span className="hidden sm:inline">Send</span>
                  </button>
                </form>
              </div>
            </div>

            {/* Right Column: Telemetry & Knowledge Inspector */}
            <div className="hidden md:flex flex-col md:col-span-4 bg-black/40 p-4 space-y-3.5 overflow-y-auto">
              <div className="flex items-center justify-between border-b border-white/10 pb-2">
                <span className="font-mono text-[10px] uppercase tracking-widest text-muted-foreground">
                  Runtime Telemetry
                </span>
                <span className="font-mono text-[10px] text-emerald-400 flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Synced
                </span>
              </div>

              {/* Active Character Profile */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 space-y-1.5">
                <div className="text-[10px] font-mono text-muted-foreground uppercase">
                  Persona & Pipeline
                </div>
                <div className="font-display text-sm font-semibold text-foreground">
                  {character.name}
                </div>
                <div className="text-xs text-muted-foreground">{character.role}</div>
                <div className="mt-2 flex items-center justify-between pt-2 border-t border-white/5 font-mono text-[10px]">
                  <span className="text-muted-foreground">Model Engine:</span>
                  <span className="text-foreground/90">{character.systemModel}</span>
                </div>
              </div>

              {/* Lore Grounding (RAG) */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 space-y-1.5">
                <div className="flex items-center justify-between text-[10px] font-mono uppercase text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Database className="h-3 w-3 text-brand" />
                    Lore Grounding (RAG)
                  </span>
                  <span className="text-emerald-400">94% match</span>
                </div>
                <div className="rounded-lg bg-black/60 p-2 font-mono text-[10.5px] text-foreground/80 leading-relaxed border border-white/5">
                  {activeLoreChunk || character.defaultLore[0]}
                </div>
              </div>

              {/* Episodic Memory */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 space-y-1.5">
                <div className="flex items-center justify-between text-[10px] font-mono uppercase text-muted-foreground">
                  <span className="flex items-center gap-1">
                    <Brain className="h-3 w-3 text-[oklch(0.75_0.15_295)]" />
                    Episodic Memory
                  </span>
                  <span className="text-foreground/60">Persistent</span>
                </div>
                <div className="rounded-lg bg-black/60 p-2 font-mono text-[10.5px] text-foreground/80 leading-relaxed border border-white/5">
                  {activeMemory || "State initialized. Context retention window active."}
                </div>
              </div>

              {/* Latency & Throughput */}
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-3 font-mono text-[10px] space-y-1">
                <div className="flex justify-between text-muted-foreground">
                  <span>First Token Latency:</span>
                  <span className="text-foreground font-semibold">{lastLatency} ms</span>
                </div>
                <div className="flex justify-between text-muted-foreground">
                  <span>Vector Index:</span>
                  <span className="text-foreground">Qdrant HNSW</span>
                </div>
                <div className="flex justify-between text-muted-foreground">
                  <span>Protocol:</span>
                  <span className="text-foreground">gRPC / WebSocket</span>
                </div>
              </div>
            </div>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
}
