import { motion, useScroll, useTransform, useMotionValueEvent } from "framer-motion";
import { useState, useEffect, useRef } from "react";
import { SectionHeader } from "./SectionHeader";
import {
  Brain,
  Cpu,
  Database,
  Layers,
  MessageSquare,
  Search,
  Sparkles,
  User,
  Play,
  Pause,
  RotateCcw,
  CheckCircle2,
  Terminal,
  Activity,
  GitBranch,
  SlidersHorizontal,
} from "lucide-react";

type Layer = {
  id: string;
  stepNumber: string;
  icon: React.ReactNode;
  name: string;
  category: "Client" | "Orchestrator" | "Knowledge" | "Model";
  note: string;
  span: string;
  ms: number;
  swappable: string;
  payload: {
    params?: Record<string, string>;
    metrics?: Record<string, string | number>;
  };
};

const SAMPLE_PROMPTS = [
  {
    label: "Guard Query",
    prompt: "Who commands the Whiterun guard?",
    character: "Guard Valerius",
    npcResponse: "Commander Caius leads the garrison. State your business, stranger.",
  },
  {
    label: "Lore Check",
    prompt: "Have dragon sightings been confirmed near High Hrothgar?",
    character: "Lorekeeper Maelor",
    npcResponse: "Aye, the Greybeards sent word yesterday. Ancient wings touch the frost.",
  },
  {
    label: "Memory Recall",
    prompt: "Do you remember when we fought the bandits at Riverwood?",
    character: "Mercenary Erik",
    npcResponse: "How could I forget? Your blade saved my life near the riverbank.",
  },
];

const layers: Layer[] = [
  {
    id: "player",
    stepNumber: "01",
    icon: <User className="h-3.5 w-3.5 text-foreground/70" />,
    name: "Player Input",
    category: "Client",
    note: "Captures player speech or text from engine runtime.",
    span: "input.capture",
    ms: 8,
    swappable: "Unreal 5, Unity, WebGL",
    payload: {
      params: {
        engine: "UnrealEngine_5.4",
        player_id: "usr_sk_9912",
        modality: "Voice & Text",
      },
      metrics: {
        audio_sample_rate: "48kHz",
      },
    },
  },
  {
    id: "api",
    stepNumber: "02",
    icon: <Layers className="h-3.5 w-3.5 text-foreground/70" />,
    name: "Sentient API Gateway",
    category: "Orchestrator",
    note: "High-throughput gRPC endpoint with streaming.",
    span: "api.route",
    ms: 4,
    swappable: "gRPC, WebSocket, HTTP/2",
    payload: {
      params: {
        protocol: "HTTP/2 (Streaming)",
        region: "us-east (iad-1)",
      },
      metrics: {
        gateway_overhead: "1.2ms",
      },
    },
  },
  {
    id: "runtime",
    stepNumber: "03",
    icon: <Cpu className="h-3.5 w-3.5 text-foreground/70" />,
    name: "Runtime Context",
    category: "Orchestrator",
    note: "Assembles persona, scene state & faction rules.",
    span: "context.compose",
    ms: 12,
    swappable: "Dynamic State Engine",
    payload: {
      params: {
        npc_id: "npc_guard_valerius",
        disposition: "vigilant",
      },
      metrics: {
        persona_tokens: 142,
      },
    },
  },
  {
    id: "memory",
    stepNumber: "04",
    icon: <Brain className="h-3.5 w-3.5 text-foreground/70" />,
    name: "Memory Engine",
    category: "Knowledge",
    note: "Retrieves short & long-term character memories.",
    span: "memory.read",
    ms: 14,
    swappable: "Redis Graph, Mem0, Supabase",
    payload: {
      params: {
        player_affinity: "+45 (Friendly)",
        last_seen: "14 mins ago",
      },
      metrics: {
        memory_window: "8,000 tokens",
      },
    },
  },
  {
    id: "retriever",
    stepNumber: "05",
    icon: <Search className="h-3.5 w-3.5 text-foreground/70" />,
    name: "Hybrid Retriever",
    category: "Knowledge",
    note: "Dense vector similarity + BM25 keyword ranking.",
    span: "retrieve.topk",
    ms: 22,
    swappable: "Dense RRF, Cohere Rerank",
    payload: {
      params: {
        strategy: "Dense + BM25 RRF",
        top_k: "3 passages",
      },
      metrics: {
        similarity_score: 0.942,
      },
    },
  },
  {
    id: "vectors",
    stepNumber: "06",
    icon: <Database className="h-3.5 w-3.5 text-foreground/70" />,
    name: "Vector Store",
    category: "Knowledge",
    note: "Indexed world lore, history & dialogue rules.",
    span: "vectors.query",
    ms: 18,
    swappable: "Pinecone, Qdrant, pgvector",
    payload: {
      params: {
        index: "world_lore_v4",
        distance: "cosine",
      },
      metrics: {
        total_vectors: "450,000",
      },
    },
  },
  {
    id: "llm",
    stepNumber: "07",
    icon: <Sparkles className="h-3.5 w-3.5 text-foreground/70" />,
    name: "Language Model",
    category: "Model",
    note: "Streams in-character dialogue via cloud or local LLM.",
    span: "llm.stream",
    ms: 34,
    swappable: "OpenAI GPT-4o, Claude 3.5, Llama 3",
    payload: {
      params: {
        model: "gpt-4o-mini",
        temperature: "0.72",
      },
      metrics: {
        first_token: "34ms",
      },
    },
  },
  {
    id: "npc",
    stepNumber: "08",
    icon: <MessageSquare className="h-3.5 w-3.5 text-foreground/70" />,
    name: "NPC Speech Engine",
    category: "Client",
    note: "Delivers streamed text and lip-sync TTS to game.",
    span: "npc.speak",
    ms: 10,
    swappable: "ElevenLabs, Inworld TTS",
    payload: {
      params: {
        voice_id: "guard_nordic_03",
        emotion: "vigilant",
      },
      metrics: {
        total_round_trip: "122 ms",
      },
    },
  },
];

const totalMs = layers.reduce((acc, curr) => acc + curr.ms, 0);
const ease = [0.22, 1, 0.36, 1] as const;

export function Architecture() {
  const [activeStepIndex, setActiveStepIndex] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isScrollDriven, setIsScrollDriven] = useState<boolean>(true);
  const [selectedPromptIndex, setSelectedPromptIndex] = useState<number>(0);
  const [activeTab, setActiveTab] = useState<"flow" | "matrix" | "telemetry">("flow");
  const [swappedEngines, setSwappedEngines] = useState<Record<string, string>>({
    vectors: "Qdrant",
    llm: "GPT-4o",
    memory: "Redis",
  });

  const pipelineRef = useRef<HTMLDivElement>(null);

  // Pinning scroll integration: target outer 250vh container
  const { scrollYProgress } = useScroll({
    target: pipelineRef,
    offset: ["start start", "end end"],
  });

  const scrollBeamScaleY = useTransform(scrollYProgress, [0, 1], [0, 1]);

  useMotionValueEvent(scrollYProgress, "change", (latest) => {
    if (isScrollDriven && !isPlaying && activeTab === "flow") {
      const stepCount = layers.length;
      const index = Math.min(stepCount - 1, Math.max(0, Math.floor(latest * stepCount)));
      setActiveStepIndex(index);
    }
  });

  const activeStep = layers[activeStepIndex];
  const activePrompt = SAMPLE_PROMPTS[selectedPromptIndex];

  // Simulation timer effect
  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (isPlaying) {
      const currentLayer = layers[activeStepIndex];
      const delay = Math.max(350, currentLayer.ms * 20);

      timer = setTimeout(() => {
        if (activeStepIndex < layers.length - 1) {
          setActiveStepIndex((prev) => prev + 1);
        } else {
          setIsPlaying(false);
        }
      }, delay);
    }
    return () => clearTimeout(timer);
  }, [isPlaying, activeStepIndex]);

  const handleStartSimulation = () => {
    setIsScrollDriven(false);
    setActiveStepIndex(0);
    setIsPlaying(true);
  };

  const handlePauseSimulation = () => {
    setIsPlaying(false);
  };

  const handleResetSimulation = () => {
    setIsPlaying(false);
    setIsScrollDriven(true);
    setActiveStepIndex(0);
  };

  return (
    <section id="architecture" ref={pipelineRef} className="relative h-[250vh]">
      {/* Sticky Pinned Container: holds section on screen below fixed navbar */}
      <div className="sticky top-20 min-h-[calc(100vh-5rem)] flex flex-col justify-center py-4">
        <div className="relative mx-auto max-w-6xl px-6 w-full">
          <SectionHeader
            eyebrow="Architecture"
            title={
              <>
                One request,
                <span className="text-foreground/45"> eight steps.</span>
              </>
            }
            description="A player says something. Sentient gathers the character's memory and lore, asks a model, and speaks back in character — in about a tenth of a second."
          />

          {/* View Switcher & Interactive Controls */}
          <div className="mt-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-white/[0.07] pb-3">
            {/* Tabs */}
            <div className="flex items-center gap-1 rounded-full border border-white/10 bg-white/[0.02] p-1 text-[11px]">
              <button
                onClick={() => setActiveTab("flow")}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1 font-mono transition-all duration-300 ${
                  activeTab === "flow"
                    ? "bg-white/10 text-foreground"
                    : "text-foreground/50 hover:text-foreground/80"
                }`}
              >
                <GitBranch className="h-3 w-3" />
                <span>Pipeline Flow</span>
              </button>

              <button
                onClick={() => setActiveTab("telemetry")}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1 font-mono transition-all duration-300 ${
                  activeTab === "telemetry"
                    ? "bg-white/10 text-foreground"
                    : "text-foreground/50 hover:text-foreground/80"
                }`}
              >
                <Activity className="h-3 w-3" />
                <span>Span Trace</span>
              </button>

              <button
                onClick={() => setActiveTab("matrix")}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1 font-mono transition-all duration-300 ${
                  activeTab === "matrix"
                    ? "bg-white/10 text-foreground"
                    : "text-foreground/50 hover:text-foreground/80"
                }`}
              >
                <SlidersHorizontal className="h-3 w-3" />
                <span>Swappable Stack</span>
              </button>
            </div>

            {/* Prompt Selector & Simulation Controls */}
            <div className="flex items-center gap-2.5">
              <div className="hidden lg:flex items-center gap-1.5 text-[10px] font-mono text-foreground/40">
                <span>Prompt:</span>
                <div className="flex items-center gap-1 rounded-full border border-white/[0.08] bg-white/[0.03] p-0.5">
                  {SAMPLE_PROMPTS.map((p, idx) => (
                    <button
                      key={idx}
                      onClick={() => {
                        setSelectedPromptIndex(idx);
                        handleResetSimulation();
                      }}
                      className={`rounded-full px-2.5 py-1 text-[10px] font-mono transition-all duration-300 ${
                        selectedPromptIndex === idx
                          ? "bg-white/10 text-foreground"
                          : "text-foreground/45 hover:text-foreground/80"
                      }`}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-center gap-1.5">
                {!isPlaying ? (
                  <button
                    onClick={handleStartSimulation}
                    className="flex items-center gap-1.5 rounded-full border border-white/15 bg-white/10 px-3 py-1 text-[11px] font-mono text-foreground transition-all duration-300 hover:bg-white/20 active:scale-95"
                  >
                    <Play className="h-2.5 w-2.5 fill-foreground" />
                    <span>{activeStepIndex === layers.length - 1 ? "Replay" : "Simulate"}</span>
                  </button>
                ) : (
                  <button
                    onClick={handlePauseSimulation}
                    className="flex items-center gap-1.5 rounded-full border border-white/20 bg-white/10 px-3 py-1 text-[11px] font-mono text-foreground transition-all duration-300 hover:bg-white/20 active:scale-95"
                  >
                    <Pause className="h-2.5 w-2.5" />
                    <span>Pause</span>
                  </button>
                )}

                <button
                  onClick={handleResetSimulation}
                  title="Reset simulation"
                  className="flex h-6 w-6 items-center justify-center rounded-full border border-white/10 bg-white/[0.03] text-foreground/50 transition-colors hover:border-white/20 hover:text-foreground"
                >
                  <RotateCcw className="h-2.5 w-2.5" />
                </button>
              </div>
            </div>
          </div>

          {/* TAB 1: PIPELINE FLOW (Sticky Pinned Stream) */}
          {activeTab === "flow" && (
            <div className="mt-5 grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
              {/* Left side: Scroll Rail + Compact Step Nodes */}
              <div className="lg:col-span-7">
                <div className="flex gap-2.5">
                  {/* Scroll progress rail */}
                  <div className="hidden sm:flex flex-col items-center pt-3 pb-3 shrink-0">
                    <div className="relative w-px h-full bg-white/[0.07]">
                      <motion.div
                        style={{ scaleY: scrollBeamScaleY, transformOrigin: "top" }}
                        className="absolute inset-0 w-full bg-[oklch(0.68_0.11_45)]"
                      />
                    </div>
                  </div>

                  {/* Compact Step Nodes (8 Steps) */}
                  <div className="flex-1 space-y-1.5">
                    {layers.map((layer, index) => {
                      const isActive = index === activeStepIndex;
                      const isPassed = index < activeStepIndex;

                      return (
                        <motion.div
                          key={layer.id}
                          onClick={() => {
                            setIsScrollDriven(false);
                            setActiveStepIndex(index);
                            setIsPlaying(false);
                          }}
                          initial={{ opacity: 0, y: 6 }}
                          animate={{ opacity: 1, y: 0 }}
                          transition={{ duration: 0.25 }}
                          className={`group relative cursor-pointer rounded-lg border px-3 py-2 transition-all duration-200 ${
                            isActive
                              ? "border-white/30 bg-white/[0.06] shadow-sm"
                              : isPassed
                                ? "border-white/[0.08] bg-white/[0.015] hover:border-white/15"
                                : "border-white/[0.05] bg-white/[0.005] opacity-60 hover:opacity-100 hover:border-white/12"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3 min-w-0">
                              <span className="w-4 font-mono text-[10px] text-foreground/30">
                                {layer.stepNumber}
                              </span>

                              <div
                                className={`flex h-6.5 w-6.5 shrink-0 items-center justify-center rounded-full border transition-colors duration-200 ${
                                  isActive
                                    ? "border-white/30 bg-white/10 text-foreground"
                                    : "border-white/10 text-foreground/50 group-hover:border-white/20 group-hover:text-foreground/80"
                                }`}
                              >
                                {layer.icon}
                              </div>

                              <div className="min-w-0">
                                <div className="font-display text-[13.5px] font-medium leading-tight text-foreground truncate">
                                  {layer.name}
                                </div>
                                <div className="mt-0.5 text-[11px] text-foreground/45 truncate">
                                  {layer.note}
                                </div>
                              </div>
                            </div>

                            <div className="text-right shrink-0 min-w-[45px]">
                              <div className="font-mono text-[11px] text-foreground/70 whitespace-nowrap">
                                {layer.ms} ms
                              </div>
                            </div>
                          </div>
                        </motion.div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Right side: Compact Telemetry & Inspector Panel */}
              <div className="lg:col-span-5 space-y-3 relative z-20 lg:sticky lg:top-24">
                <motion.div
                  key={activeStep.id}
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  transition={{ duration: 0.15 }}
                  className="rounded-xl border border-white/10 bg-background p-4 relative"
                >
                  {/* Header */}
                  <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-7.5 w-7.5 items-center justify-center rounded-lg border border-white/15 bg-white/5">
                        {activeStep.icon}
                      </div>
                      <div>
                        <div className="font-mono text-[9px] text-foreground/40 uppercase tracking-widest">
                          STEP {activeStep.stepNumber} · {activeStep.category}
                        </div>
                        <div className="font-display text-sm font-semibold text-foreground">
                          {activeStep.name}
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <div className="font-mono text-xs font-semibold text-foreground">
                        {activeStep.ms} ms
                      </div>
                      <div className="font-mono text-[9px] text-foreground/30 uppercase">
                        {activeStep.span}
                      </div>
                    </div>
                  </div>

                  <p className="mt-2.5 text-[11px] text-foreground/60 leading-relaxed">
                    {activeStep.note}
                  </p>

                  {/* Swappable indicator */}
                  <div className="mt-2.5 font-mono text-[10px] text-foreground/40 border-t border-white/[0.06] pt-2 flex justify-between">
                    <span>Swappable:</span>
                    <span className="text-foreground/80">{activeStep.swappable}</span>
                  </div>

                  {/* Telemetry Payload Code Inspector */}
                  <div className="mt-2.5 rounded-lg border border-white/10 bg-black/50 p-2.5 font-mono text-[10px] overflow-hidden">
                    <div className="flex items-center justify-between text-foreground/40 pb-1.5 border-b border-white/10 text-[9px] uppercase tracking-wider">
                      <span className="flex items-center gap-1">
                        <Terminal className="h-3 w-3 text-foreground/50" />
                        Span Payload
                      </span>
                      <span>{activeStep.span}</span>
                    </div>

                    <div className="mt-1.5 space-y-1 text-foreground/80">
                      <div>
                        <span className="text-[oklch(0.88_0.09_80)]">params: </span>
                        <span className="text-foreground/40">&#123;</span>
                      </div>
                      {Object.entries(activeStep.payload.params || {}).map(([key, val]) => (
                        <div key={key} className="pl-3 flex justify-between gap-2">
                          <span className="text-foreground/40 shrink-0">{key}:</span>
                          <span className="text-[oklch(0.82_0.12_150)] truncate max-w-[150px]">
                            "{val}"
                          </span>
                        </div>
                      ))}
                      <div>
                        <span className="text-foreground/40">&#125;</span>
                      </div>
                    </div>
                  </div>

                  {/* Response output preview on step 8 */}
                  {activeStepIndex === layers.length - 1 && (
                    <motion.div
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="mt-2.5 rounded-lg border border-white/15 bg-white/[0.04] p-2.5 text-[11px]"
                    >
                      <div className="flex items-center gap-1 font-mono text-[9px] text-foreground/50 uppercase tracking-wider mb-0.5">
                        <CheckCircle2 className="h-3 w-3 text-brand" />
                        <span>Stream Response (122ms)</span>
                      </div>
                      <p className="text-foreground/90 italic mt-0.5 text-xs">
                        "{activePrompt.npcResponse}"
                      </p>
                    </motion.div>
                  )}
                </motion.div>

                {/* Total SLA Metric Card */}
                <div className="rounded-xl border border-white/10 bg-background p-3 font-mono text-[11px] space-y-1.5">
                  <div className="flex justify-between items-center text-foreground/40 text-[9px] uppercase tracking-wider">
                    <span>Round Trip Latency</span>
                    <span>P99 &lt; 150ms</span>
                  </div>

                  <div className="space-y-1">
                    <div className="flex justify-between text-foreground/80 text-[11px]">
                      <span>Total execution</span>
                      <span className="font-semibold text-foreground">{totalMs} ms</span>
                    </div>
                    <div className="h-1 w-full rounded-full bg-white/10 overflow-hidden">
                      <div className="h-full bg-[oklch(0.68_0.11_45)] w-full" />
                    </div>
                  </div>

                  <div className="flex justify-between text-[9px] text-foreground/40 pt-1 border-t border-white/5">
                    <span>Memory: 1.2 MB</span>
                    <span>Engine-agnostic</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 2: TRACE TELEMETRY */}
          {activeTab === "telemetry" && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-5 rounded-xl border border-white/10 bg-black/40 overflow-hidden"
            >
              <div className="p-3 border-b border-white/10 bg-white/[0.02] flex items-center justify-between font-mono text-xs">
                <span className="text-foreground/60 flex items-center gap-2 text-[11px]">
                  <Terminal className="h-3.5 w-3.5" />
                  Pipeline Span Trace Log
                </span>
                <span className="text-foreground/40 text-[10px] uppercase">8 Spans</span>
              </div>

              <div className="divide-y divide-white/[0.06]">
                {layers.map((layer, index) => (
                  <div
                    key={layer.id}
                    onClick={() => {
                      setActiveStepIndex(index);
                      setActiveTab("flow");
                    }}
                    className="grid grid-cols-12 items-center px-4 py-2.5 text-[11px] font-mono hover:bg-white/[0.03] cursor-pointer transition-colors"
                  >
                    <div className="col-span-1 text-foreground/30">{layer.stepNumber}</div>
                    <div className="col-span-4 font-medium text-foreground flex items-center gap-2">
                      <span className="text-foreground/50">{layer.icon}</span>
                      <span>{layer.name}</span>
                    </div>
                    <div className="col-span-3 text-foreground/40 text-[10px] truncate">
                      {layer.span}
                    </div>
                    <div className="col-span-2 text-foreground/50 truncate text-[10px]">
                      {layer.swappable}
                    </div>
                    <div className="col-span-2 text-right text-foreground/80 font-semibold">
                      {layer.ms} ms
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}

          {/* TAB 3: SWAPPABLE STACK MATRIX */}
          {activeTab === "matrix" && (
            <motion.div
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-4"
            >
              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg border border-white/10 bg-white/5 text-foreground">
                    <Database className="h-3.5 w-3.5" />
                  </div>
                  <div>
                    <h4 className="font-display text-xs font-semibold text-foreground">
                      Vector Store
                    </h4>
                    <p className="text-[10px] text-foreground/50">Indexed database</p>
                  </div>
                </div>

                <div className="space-y-1 pt-0.5">
                  {["Pinecone", "Qdrant", "pgvector (Postgres)", "Milvus", "Supabase Vector"].map(
                    (opt) => (
                      <button
                        key={opt}
                        onClick={() => setSwappedEngines((prev) => ({ ...prev, vectors: opt }))}
                        className={`w-full text-left px-2.5 py-1.5 rounded-lg border text-[11px] font-mono transition-all flex items-center justify-between ${
                          swappedEngines.vectors === opt
                            ? "border-white/30 bg-white/10 text-foreground"
                            : "border-white/5 bg-white/[0.01] text-foreground/60 hover:border-white/15"
                        }`}
                      >
                        <span>{opt}</span>
                        {swappedEngines.vectors === opt && (
                          <CheckCircle2 className="h-3 w-3 text-foreground/80" />
                        )}
                      </button>
                    ),
                  )}
                </div>
              </div>

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg border border-white/10 bg-white/5 text-foreground">
                    <Sparkles className="h-3.5 w-3.5" />
                  </div>
                  <div>
                    <h4 className="font-display text-xs font-semibold text-foreground">
                      Language Model
                    </h4>
                    <p className="text-[10px] text-foreground/50">Hosted cloud or local LLM</p>
                  </div>
                </div>

                <div className="space-y-1 pt-0.5">
                  {[
                    "OpenAI GPT-4o",
                    "Claude 3.5 Sonnet",
                    "Ollama (Local Llama 3)",
                    "Mistral Large",
                    "Groq (Sub-50ms)",
                  ].map((opt) => (
                    <button
                      key={opt}
                      onClick={() => setSwappedEngines((prev) => ({ ...prev, llm: opt }))}
                      className={`w-full text-left px-2.5 py-1.5 rounded-lg border text-[11px] font-mono transition-all flex items-center justify-between ${
                        swappedEngines.llm === opt
                          ? "border-white/30 bg-white/10 text-foreground"
                          : "border-white/5 bg-white/[0.01] text-foreground/60 hover:border-white/15"
                      }`}
                    >
                      <span>{opt}</span>
                      {swappedEngines.llm === opt && (
                        <CheckCircle2 className="h-3 w-3 text-foreground/80" />
                      )}
                    </button>
                  ))}
                </div>
              </div>

              <div className="rounded-xl border border-white/10 bg-white/[0.02] p-4 space-y-3">
                <div className="flex items-center gap-2.5">
                  <div className="p-1.5 rounded-lg border border-white/10 bg-white/5 text-foreground">
                    <Brain className="h-3.5 w-3.5" />
                  </div>
                  <div>
                    <h4 className="font-display text-xs font-semibold text-foreground">
                      Memory Provider
                    </h4>
                    <p className="text-[10px] text-foreground/50">State & context engine</p>
                  </div>
                </div>

                <div className="space-y-1 pt-0.5">
                  {["Redis Cache", "Mem0 Platform", "PostgreSQL JSONB", "In-Memory Ephemeral"].map(
                    (opt) => (
                      <button
                        key={opt}
                        onClick={() => setSwappedEngines((prev) => ({ ...prev, memory: opt }))}
                        className={`w-full text-left px-2.5 py-1.5 rounded-lg border text-[11px] font-mono transition-all flex items-center justify-between ${
                          swappedEngines.memory === opt
                            ? "border-white/30 bg-white/10 text-foreground"
                            : "border-white/5 bg-white/[0.01] text-foreground/60 hover:border-white/15"
                        }`}
                      >
                        <span>{opt}</span>
                        {swappedEngines.memory === opt && (
                          <CheckCircle2 className="h-3 w-3 text-foreground/80" />
                        )}
                      </button>
                    ),
                  )}
                </div>
              </div>
            </motion.div>
          )}

          {/* Bottom Metrics Bar */}
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.8, ease }}
            className="mt-6 flex flex-wrap items-center justify-between gap-3 font-mono text-[10px] uppercase tracking-[0.2em] text-foreground/40 border-t border-white/[0.07] pt-3"
          >
            <span>Total · 122 ms round trip</span>
            <span>Swap any step — model, memory or store</span>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
