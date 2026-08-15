import { motion, useInView } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { Check, Copy, FileCode2 } from "lucide-react";
import { SectionHeader } from "./SectionHeader";

type CodeSnippet = {
  id: "curl" | "typescript" | "python" | "unreal";
  label: string;
  filename: string;
  badge: string;
  code: string;
  tokens: { t: string; c: "kw" | "fn" | "at" | "str" | "key" | "bool" | "pn" | "com" }[];
};

const SNIPPETS: CodeSnippet[] = [
  {
    id: "curl",
    label: "cURL",
    filename: "request.sh",
    badge: "OpenAI-Compatible",
    code: `curl https://api.sentient.dev/v1/chat/completions \\
  -H "Authorization: Bearer sk-sentient-••••" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "sentient-npc",
    "game": "skyrim",
    "npc": "whiterun_guard_14",
    "stream": true,
    "messages": [
      { "role": "user", "content": "Where is the Dragonborn?" }
    ]
  }'`,
    tokens: [
      { t: "curl ", c: "kw" },
      { t: "https://api.sentient.dev/v1/chat/completions", c: "fn" },
      { t: " \\\n  -H ", c: "at" },
      { t: '"Authorization: Bearer sk-sentient-••••"', c: "str" },
      { t: " \\\n  -H ", c: "at" },
      { t: '"Content-Type: application/json"', c: "str" },
      { t: " \\\n  -d ", c: "at" },
      { t: "'{\n    ", c: "pn" },
      { t: '"model"', c: "key" },
      { t: ": ", c: "pn" },
      { t: '"sentient-npc"', c: "str" },
      { t: ",\n    ", c: "pn" },
      { t: '"game"', c: "key" },
      { t: ": ", c: "pn" },
      { t: '"skyrim"', c: "str" },
      { t: ",\n    ", c: "pn" },
      { t: '"npc"', c: "key" },
      { t: ": ", c: "pn" },
      { t: '"whiterun_guard_14"', c: "str" },
      { t: ",\n    ", c: "pn" },
      { t: '"stream"', c: "key" },
      { t: ": ", c: "pn" },
      { t: "true", c: "bool" },
      { t: ",\n    ", c: "pn" },
      { t: '"messages"', c: "key" },
      { t: ": [\n      { ", c: "pn" },
      { t: '"role"', c: "key" },
      { t: ": ", c: "pn" },
      { t: '"user"', c: "str" },
      { t: ", ", c: "pn" },
      { t: '"content"', c: "key" },
      { t: ": ", c: "pn" },
      { t: '"Where is the Dragonborn?"', c: "str" },
      { t: " }\n    ]\n  }'", c: "pn" },
    ],
  },
  {
    id: "typescript",
    label: "TypeScript / Node",
    filename: "openai-client.ts",
    badge: "OpenAI SDK",
    code: `import OpenAI from "openai";

// Drop-in OpenAI SDK configured for Sentient API gateway
const client = new OpenAI({
  baseURL: "https://api.sentient.dev/v1",
  apiKey: process.env.SENTIENT_API_KEY,
});

const stream = await client.chat.completions.create({
  model: "sentient-npc",
  stream: true,
  messages: [{ role: "user", content: "Where is the Dragonborn?" }],
  extra_body: { game: "skyrim", npc: "whiterun_guard_14" },
});

for await (const chunk of stream) {
  process.stdout.write(chunk.choices[0]?.delta?.content || "");
}`,
    tokens: [
      { t: "import ", c: "kw" },
      { t: "OpenAI ", c: "fn" },
      { t: "from ", c: "kw" },
      { t: '"openai"', c: "str" },
      { t: ";\n\n", c: "pn" },
      { t: "// Drop-in OpenAI SDK configured for Sentient API gateway\n", c: "com" },
      { t: "const ", c: "kw" },
      { t: "client ", c: "fn" },
      { t: "= ", c: "pn" },
      { t: "new ", c: "kw" },
      { t: "OpenAI", c: "fn" },
      { t: "({\n  baseURL: ", c: "pn" },
      { t: '"https://api.sentient.dev/v1"', c: "str" },
      { t: ",\n  apiKey: ", c: "pn" },
      { t: "process.env.SENTIENT_API_KEY", c: "key" },
      { t: ",\n});\n\n", c: "pn" },
      { t: "const ", c: "kw" },
      { t: "stream ", c: "fn" },
      { t: "= ", c: "pn" },
      { t: "await ", c: "kw" },
      { t: "client.chat.completions.", c: "fn" },
      { t: "create", c: "key" },
      { t: "({\n  model: ", c: "pn" },
      { t: '"sentient-npc"', c: "str" },
      { t: ",\n  stream: ", c: "pn" },
      { t: "true", c: "bool" },
      { t: ",\n  messages: [{ role: ", c: "pn" },
      { t: '"user"', c: "str" },
      { t: ", content: ", c: "pn" },
      { t: '"Where is the Dragonborn?"', c: "str" },
      { t: " }],\n  extra_body: { game: ", c: "pn" },
      { t: '"skyrim"', c: "str" },
      { t: ", npc: ", c: "pn" },
      { t: '"whiterun_guard_14"', c: "str" },
      { t: " },\n});\n\n", c: "pn" },
      { t: "for await ", c: "kw" },
      { t: "(", c: "pn" },
      { t: "const ", c: "kw" },
      { t: "chunk ", c: "fn" },
      { t: "of ", c: "kw" },
      { t: "stream) {\n  ", c: "pn" },
      { t: "process.stdout.write", c: "fn" },
      { t: "(chunk.choices[0]?.delta?.content || ", c: "pn" },
      { t: '""', c: "str" },
      { t: ");\n}", c: "pn" },
    ],
  },
  {
    id: "python",
    label: "Python",
    filename: "openai_client.py",
    badge: "OpenAI Library",
    code: `from openai import OpenAI
import os

# Connect game runtime to Sentient OpenAI-compatible gateway
client = OpenAI(
    base_url="https://api.sentient.dev/v1",
    api_key=os.environ.get("SENTIENT_API_KEY")
)

stream = client.chat.completions.create(
    model="sentient-npc",
    stream=True,
    messages=[{"role": "user", "content": "Where is the Dragonborn?"}],
    extra_body={"game": "skyrim", "npc": "whiterun_guard_14"}
)

for chunk in stream:
    print(chunk.choices[0].delta.content or "", end="", flush=True)`,
    tokens: [
      { t: "from ", c: "kw" },
      { t: "openai ", c: "fn" },
      { t: "import ", c: "kw" },
      { t: "OpenAI\n", c: "fn" },
      { t: "import ", c: "kw" },
      { t: "os\n\n", c: "fn" },
      { t: "# Connect game runtime to Sentient OpenAI-compatible gateway\n", c: "com" },
      { t: "client ", c: "fn" },
      { t: "= ", c: "pn" },
      { t: "OpenAI", c: "fn" },
      { t: "(\n    base_url=", c: "pn" },
      { t: '"https://api.sentient.dev/v1"', c: "str" },
      { t: ",\n    api_key=", c: "pn" },
      { t: 'os.environ.get("SENTIENT_API_KEY")', c: "key" },
      { t: "\n)\n\n", c: "pn" },
      { t: "stream = client.chat.completions.", c: "fn" },
      { t: "create", c: "key" },
      { t: "(\n    model=", c: "pn" },
      { t: '"sentient-npc"', c: "str" },
      { t: ",\n    stream=", c: "pn" },
      { t: "True", c: "bool" },
      {
        t: ',\n    messages=[{"role": "user", "content": "Where is the Dragonborn?"}],\n    extra_body={"game": "skyrim", "npc": "whiterun_guard_14"}\n)\n\n',
        c: "pn",
      },
      { t: "for ", c: "kw" },
      { t: "chunk ", c: "fn" },
      { t: "in ", c: "kw" },
      { t: "stream:\n    ", c: "pn" },
      { t: "print", c: "fn" },
      { t: '(chunk.choices[0].delta.content or "", end="", flush=True)', c: "pn" },
    ],
  },
  {
    id: "unreal",
    label: "Unreal / Unity HTTP",
    filename: "GameClientRequest.cpp",
    badge: "HTTP REST / gRPC",
    code: `// Standard OpenAI-compatible HTTP POST from game client
TSharedRef<IHttpRequest> Request = FHttpModule::Get().CreateRequest();
Request->SetURL(TEXT("https://api.sentient.dev/v1/chat/completions"));
Request->SetVerb(TEXT("POST"));
Request->SetHeader(TEXT("Authorization"), FString::Printf(TEXT("Bearer %s"), *ApiKey));
Request->SetHeader(TEXT("Content-Type"), TEXT("application/json"));
Request->SetContentAsString(JsonPayload);
Request->ProcessRequest();`,
    tokens: [
      { t: "// Standard OpenAI-compatible HTTP POST from game client\n", c: "com" },
      { t: "TSharedRef<IHttpRequest> ", c: "kw" },
      { t: "Request = FHttpModule::Get().CreateRequest();\n", c: "fn" },
      { t: "Request->", c: "pn" },
      { t: "SetURL", c: "key" },
      { t: "(", c: "pn" },
      { t: 'TEXT("https://api.sentient.dev/v1/chat/completions")', c: "str" },
      { t: ");\n", c: "pn" },
      { t: "Request->", c: "pn" },
      { t: "SetVerb", c: "key" },
      { t: "(", c: "pn" },
      { t: 'TEXT("POST")', c: "str" },
      { t: ");\n", c: "pn" },
      { t: "Request->", c: "pn" },
      { t: "SetHeader", c: "key" },
      { t: "(", c: "pn" },
      { t: 'TEXT("Authorization")', c: "str" },
      { t: ", ", c: "pn" },
      { t: 'FString::Printf(TEXT("Bearer %s"), *ApiKey)', c: "fn" },
      { t: ");\n", c: "pn" },
      { t: "Request->", c: "pn" },
      { t: "SetHeader", c: "key" },
      { t: "(", c: "pn" },
      { t: 'TEXT("Content-Type")', c: "str" },
      { t: ", ", c: "pn" },
      { t: 'TEXT("application/json")', c: "str" },
      { t: ");\n", c: "pn" },
      { t: "Request->SetContentAsString(JsonPayload);\n", c: "fn" },
      { t: "Request->ProcessRequest();", c: "fn" },
    ],
  },
];

const cls: Record<string, string> = {
  kw: "text-[oklch(0.85_0.14_295)]",
  fn: "text-[oklch(0.85_0.14_220)]",
  at: "text-[oklch(0.7_0.02_260)]",
  str: "text-[oklch(0.82_0.12_150)]",
  key: "text-[oklch(0.88_0.09_80)]",
  bool: "text-[oklch(0.85_0.14_25)]",
  pn: "text-[oklch(0.6_0.02_260)]",
  com: "text-muted-foreground/60 italic",
};

export function CodeExample() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.3 });
  const [activeTab, setActiveTab] = useState<CodeSnippet["id"]>("curl");
  const [copied, setCopied] = useState(false);
  const [n, setN] = useState(0);

  const currentSnippet = SNIPPETS.find((s) => s.id === activeTab) || SNIPPETS[0];
  const total = currentSnippet.code.length;

  useEffect(() => {
    if (!inView) return;
    setN(0);
    let i = 0;
    const id = setInterval(() => {
      i += 8;
      setN((prev) => {
        const next = Math.min(i, total);
        if (next >= total) clearInterval(id);
        return next;
      });
    }, 16);
    return () => clearInterval(id);
  }, [inView, activeTab, total]);

  const handleCopy = () => {
    navigator.clipboard.writeText(currentSnippet.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  let remaining = n;
  const rendered = currentSnippet.tokens.map((tok, i) => {
    if (remaining <= 0) return <span key={i} />;
    const slice = tok.t.slice(0, remaining);
    remaining -= tok.t.length;
    return (
      <span key={i} className={cls[tok.c]}>
        {slice}
      </span>
    );
  });

  return (
    <section id="docs" ref={ref} className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <SectionHeader
          eyebrow="OpenAI-Compatible API Gateway"
          title={<>One endpoint. Standard OpenAI format.</>}
          description="Sentient is an OpenAI-compatible API gateway and authentication platform. Connect multiple AI APIs, custom models, and retrieval pipelines directly into Mantella, Unreal, Unity, or any game client."
        />

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          className="glass-strong mx-auto mt-14 max-w-3xl overflow-hidden rounded-3xl"
        >
          {/* Header Bar with Tabs and Copy Button */}
          <div className="flex flex-wrap items-center justify-between border-b border-border/60 bg-black/40 px-4 py-2.5 gap-2">
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5 mr-2">
                <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.7_0.18_25)]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.8_0.15_90)]" />
                <span className="h-2.5 w-2.5 rounded-full bg-[oklch(0.75_0.16_150)]" />
              </div>

              {/* Language Switcher */}
              <div className="flex items-center gap-1 overflow-x-auto">
                {SNIPPETS.map((s) => (
                  <button
                    key={s.id}
                    onClick={() => setActiveTab(s.id)}
                    className={`rounded-lg px-2.5 py-1 font-mono text-[11px] transition-all cursor-pointer ${
                      activeTab === s.id
                        ? "bg-white/15 text-foreground shadow-sm font-semibold"
                        : "text-muted-foreground hover:bg-white/[0.04] hover:text-foreground"
                    }`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden sm:inline-block rounded-full border border-border/60 px-2 py-0.5 font-mono text-[10px] text-muted-foreground">
                {currentSnippet.badge}
              </span>

              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 rounded-lg border border-border/60 bg-white/[0.03] px-2.5 py-1 font-mono text-[11px] text-muted-foreground transition-colors hover:border-white/20 hover:text-foreground active:scale-95 cursor-pointer"
                title="Copy snippet"
              >
                {copied ? (
                  <>
                    <Check className="h-3 w-3 text-emerald-400" />
                    <span className="text-emerald-400">Copied!</span>
                  </>
                ) : (
                  <>
                    <Copy className="h-3 w-3" />
                    <span>Copy</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {/* Subheader showing filename */}
          <div className="flex items-center justify-between border-b border-white/[0.04] bg-black/20 px-4 py-1.5 text-[11px] font-mono text-muted-foreground/70">
            <span className="flex items-center gap-1.5">
              <FileCode2 className="h-3 w-3 text-brand" />
              {currentSnippet.filename}
            </span>
            <span>UTF-8</span>
          </div>

          {/* Code Window */}
          <pre className="overflow-x-auto p-6 font-mono text-[13px] leading-relaxed min-h-[220px]">
            <code>
              {rendered}
              {n < total && (
                <span className="animate-caret ml-0.5 inline-block h-4 w-[2px] translate-y-[3px] bg-foreground" />
              )}
            </code>
          </pre>
        </motion.div>
      </div>
    </section>
  );
}
