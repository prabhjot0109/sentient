import { motion } from "framer-motion";
import { GITHUB_REPO_URL } from "@/lib/site";

export function Vision() {
  return (
    <section id="launch" className="relative py-32 md:py-40">
      <div className="mx-auto max-w-5xl px-6">
        <div className="glass-strong relative overflow-hidden rounded-[36px] p-10 sm:p-16 text-center ring-glow">
          <div className="dot-bg absolute inset-0 -z-10 opacity-30" />

          <motion.p
            initial={{ opacity: 0, y: 8 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="font-mono text-[10px] uppercase tracking-[0.25em] text-muted-foreground"
          >
            The future
          </motion.p>
          <motion.h2
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="mt-6 text-[clamp(2.4rem,6vw,5rem)] font-semibold leading-[0.98] tracking-[-0.03em]"
          >
            <span className="text-foreground">One platform.</span>{" "}
            <span className="text-brand">Infinite worlds.</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.1 }}
            className="mx-auto mt-6 max-w-xl text-base text-muted-foreground sm:text-lg leading-relaxed"
          >
            Today Skyrim. Tomorrow every game. Sentient is the OpenAI-compatible runtime and auth
            gateway for connecting multiple AI models, memories, and lore directly into game
            engines.
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 12 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ delay: 0.2 }}
            className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row"
          >
            <a href="#docs" className="btn-primary">
              Get Started
            </a>
            <a
              href={GITHUB_REPO_URL}
              target="_blank"
              rel="noopener noreferrer"
              className="btn-ghost"
            >
              View on GitHub
            </a>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
