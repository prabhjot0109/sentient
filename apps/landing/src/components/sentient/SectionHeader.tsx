import { motion } from "framer-motion";
import type { ReactNode } from "react";

const ease = [0.22, 1, 0.36, 1] as const;

export function SectionHeader({
  eyebrow,
  title,
  description,
  align = "center",
}: {
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  align?: "center" | "left";
}) {
  return (
    <div className={align === "center" ? "mx-auto max-w-xl text-center" : "max-w-xl"}>
      <motion.div
        initial={{ opacity: 0, y: 8 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ duration: 0.8, ease }}
        className={`inline-flex items-center gap-2.5 font-mono text-[10px] uppercase tracking-[0.28em] text-foreground/50 ${
          align === "center" ? "justify-center" : ""
        }`}
      >
        <span className="h-px w-6 bg-foreground/25" />
        {eyebrow}
      </motion.div>
      <motion.h2
        initial={{ opacity: 0, y: 14 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.5 }}
        transition={{ duration: 1, ease, delay: 0.08 }}
        className="mt-5 text-[clamp(2rem,4.6vw,3.75rem)] font-semibold leading-[1.02] tracking-[-0.03em] text-foreground text-balance"
      >
        {title}
      </motion.h2>
      {description && (
        <motion.p
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.9, ease, delay: 0.16 }}
          className="mx-auto mt-5 max-w-lg text-[15px] leading-[1.65] text-foreground/60 sm:text-base"
        >
          {description}
        </motion.p>
      )}
    </div>
  );
}
