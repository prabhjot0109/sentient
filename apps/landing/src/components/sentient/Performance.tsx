import { motion, useInView } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import { SectionHeader } from "./SectionHeader";

const metrics = [
  { label: "Time to first token", value: 84, suffix: "ms", desc: "Streaming from LLM to NPC" },
  { label: "Retrieval latency", value: 41, suffix: "ms", desc: "Hybrid vector + keyword" },
  { label: "Concurrent conversations", value: 12000, suffix: "+", desc: "Per runtime node" },
  { label: "Background indexing", value: 99.98, suffix: "%", desc: "Availability, 30d avg" },
];

function useCount(target: number, on: boolean) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (!on) return;
    const start = performance.now();
    const dur = 1400;
    let raf = 0;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      const eased = 1 - Math.pow(1 - p, 3);
      setN(target * eased);
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [on, target]);
  return n;
}

function Metric({ m, on }: { m: (typeof metrics)[number]; on: boolean }) {
  const n = useCount(m.value, on);
  const display =
    m.value >= 1000
      ? Math.round(n).toLocaleString()
      : m.value % 1 !== 0
        ? n.toFixed(2)
        : Math.round(n).toString();
  return (
    <div className="glass relative overflow-hidden rounded-3xl p-6">
      <div className="text-xs text-muted-foreground">{m.label}</div>
      <div className="mt-3 flex items-baseline gap-1">
        <span className="text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
          {display}
        </span>
        <span className="text-lg text-muted-foreground">{m.suffix}</span>
      </div>
      <div className="mt-2 text-xs text-muted-foreground">{m.desc}</div>
      <Spark />
    </div>
  );
}

function Spark() {
  const pts = Array.from({ length: 24 }, (_, i) => {
    const y = 20 + Math.sin(i * 0.7) * 8 + Math.sin(i * 2.3) * 2;
    return `${(i / 23) * 100},${y}`;
  }).join(" ");
  return (
    <svg viewBox="0 0 100 40" className="mt-4 h-10 w-full">
      <polyline
        points={pts}
        fill="none"
        stroke="var(--brand)"
        strokeWidth="1.4"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Performance() {
  const ref = useRef<HTMLDivElement>(null);
  const on = useInView(ref, { once: true, amount: 0.3 });
  return (
    <section ref={ref} className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <SectionHeader
          eyebrow="Performance"
          title={<>Built for real-time worlds.</>}
          description="Streaming, async indexing, and horizontally scalable. The runtime keeps up with the player."
        />
        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {metrics.map((m) => (
            <motion.div
              key={m.label}
              initial={{ opacity: 0, y: 12 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
            >
              <Metric m={m} on={on} />
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
