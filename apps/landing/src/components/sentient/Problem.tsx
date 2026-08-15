import { motion } from "framer-motion";
import { SectionHeader } from "./SectionHeader";

const oldLines = [
  { who: "Guard", text: "I used to be an adventurer like you." },
  { who: "You", text: "We just had this exact conversation." },
  { who: "Guard", text: "I used to be an adventurer like you." },
  { who: "Guard", text: "I used to be an adventurer like you." },
];

const newLines = [
  { who: "You", text: "Any word on the college in Winterhold?" },
  {
    who: "Guard",
    text: "Aye — after your last visit, half the hold's been talking. Savos still owes you thanks.",
  },
  { who: "You", text: "And the frost troll near the pass?" },
  { who: "Guard", text: "Dead. You made sure of that two winters ago." },
];

export function Problem() {
  return (
    <section className="relative py-24 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        <SectionHeader
          eyebrow="The problem"
          title={
            <>
              NPCs today are <span className="text-brand">frozen in time.</span>
            </>
          }
          description="Repetitive, scripted, forgetful. Immersion breaks the moment a guard tells you — again — that they used to be an adventurer."
        />

        <div className="mt-16 grid gap-6 md:grid-cols-2">
          <DialoguePanel title="Before Sentient" tone="dim" lines={oldLines} />
          <DialoguePanel title="With Sentient" tone="glow" lines={newLines} />
        </div>
      </div>
    </section>
  );
}

function DialoguePanel({
  title,
  tone,
  lines,
}: {
  title: string;
  tone: "dim" | "glow";
  lines: { who: string; text: string }[];
}) {
  const glow = tone === "glow";
  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.3 }}
      className={`glass relative overflow-hidden rounded-3xl p-6 ${glow ? "ring-glow" : ""}`}
    >
      {glow && (
        <div
          aria-hidden
          className="absolute inset-0 -z-10 opacity-80"
          style={{
            background: "oklch(0.68 0.11 45 / 0.06)",
          }}
        />
      )}
      <div className="mb-4 flex items-center justify-between">
        <span className="text-sm font-medium">{title}</span>
        <span
          className={`h-2 w-2 rounded-full ${glow ? "bg-[oklch(0.7_0.18_150)]" : "bg-white/20"}`}
        />
      </div>
      <ul className="space-y-3">
        {lines.map((l, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, x: l.who === "You" ? 12 : -12 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true, amount: 0.4 }}
            transition={{ delay: i * 0.08 }}
            className={`flex ${l.who === "You" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${
                l.who === "You"
                  ? "rounded-br-md bg-white/[0.06]"
                  : `rounded-bl-md border border-border/60 ${
                      glow ? "bg-white/[0.05]" : "bg-white/[0.02]"
                    }`
              } ${glow ? "" : "text-muted-foreground"}`}
            >
              <div className="mb-0.5 text-[10px] uppercase tracking-widest text-muted-foreground/80">
                {l.who}
              </div>
              {l.text}
            </div>
          </motion.li>
        ))}
      </ul>
    </motion.div>
  );
}
