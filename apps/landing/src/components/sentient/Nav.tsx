import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { Github, Menu, X } from "lucide-react";
import { Logo } from "./Logo";
import { CONSOLE_URL, GITHUB_REPO_URL } from "@/lib/site";

const links = [
  { label: "Architecture", href: "#architecture" },
  { label: "How it works", href: "#how" },
  { label: "Games", href: "#games" },
  { label: "Platform", href: "#platform" },
  { label: "Docs", href: "#docs" },
];

const sectionIds = links.map((l) => l.href.replace("#", "")).filter(Boolean);

const ease = [0.22, 1, 0.36, 1] as const;

export function Nav() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState<string | null>(null);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 48);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    if (typeof window === "undefined" || !("IntersectionObserver" in window)) return;

    const ratios = new Map<string, number>();

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          ratios.set(entry.target.id, entry.intersectionRatio);
        });

        let bestId: string | null = null;
        let bestRatio = 0;
        ratios.forEach((ratio, id) => {
          if (ratio > bestRatio) {
            bestRatio = ratio;
            bestId = id;
          }
        });

        setActiveSection(bestId);
      },
      {
        rootMargin: "-20% 0px -60% 0px",
        threshold: [0, 0.25, 0.5, 0.75, 1],
      },
    );

    sectionIds.forEach((id) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, []);

  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <AnimatePresence mode="wait" initial={false}>
        {!scrolled ? (
          <motion.div
            key="plain"
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.45, ease }}
            className="mx-auto flex h-20 max-w-[1400px] items-center justify-between px-8 md:h-24 md:px-14"
          >
            <a
              href="#top"
              className="font-display text-lg font-semibold tracking-tight text-foreground transition-opacity hover:opacity-70 flex items-center gap-2"
            >
              <Logo className="h-5 w-5" />
              <span>Sentient</span>
            </a>

            <nav className="absolute left-1/2 hidden -translate-x-1/2 items-center gap-10 md:flex">
              {links.map((l) => {
                const isActive = activeSection === l.href.replace("#", "");
                return (
                  <a
                    key={l.href}
                    href={l.href}
                    className={`relative text-[11px] font-medium uppercase tracking-[0.2em] transition-all duration-300 hover:tracking-[0.28em] ${
                      isActive
                        ? "text-foreground font-semibold"
                        : "text-foreground/75 hover:text-foreground"
                    }`}
                  >
                    {l.label}
                    {isActive && (
                      <motion.span
                        layoutId="nav-active-dot"
                        className="absolute -bottom-1.5 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full bg-brand"
                        transition={{ duration: 0.35, ease }}
                      />
                    )}
                  </a>
                );
              })}
            </nav>

            <div className="flex items-center gap-3">
              <a
                href={GITHUB_REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                aria-label="GitHub Repository"
                className="hidden p-2 text-foreground/60 transition-colors hover:text-foreground md:block"
              >
                <Github className="h-[18px] w-[18px]" />
              </a>

              <a href={CONSOLE_URL} className="hidden sm:inline-flex btn-primary">
                Get Started
              </a>

              <button
                onClick={() => setMobileMenuOpen(true)}
                className="block p-2 text-foreground/75 transition-colors hover:text-foreground md:hidden"
                aria-label="Open Menu"
              >
                <Menu className="h-5 w-5" />
              </button>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="pill"
            initial={{ opacity: 0, y: -12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -12 }}
            transition={{ duration: 0.5, ease }}
            className="flex justify-center px-4 pt-4"
          >
            <div
              className="relative flex w-full max-w-[1152px] items-center justify-between rounded-full px-4 py-2"
              style={{
                background: "oklch(1 0 0 / 0.05)",
                backdropFilter: "blur(24px) saturate(180%)",
                border: "1px solid oklch(1 0 0 / 0.12)",
                boxShadow:
                  "0 20px 60px -20px oklch(0 0 0 / 0.9), inset 0 1px 0 oklch(1 0 0 / 0.08)",
              }}
            >
              <a href="#top" className="group flex items-center gap-2.5">
                <Logo className="h-6 w-6" />
                <span className="font-display text-[15px] font-semibold tracking-tight">
                  Sentient
                </span>
              </a>

              <nav className="hidden items-center gap-0.5 md:flex">
                {links.map((l) => {
                  const isActive = activeSection === l.href.replace("#", "");
                  return (
                    <a
                      key={l.href}
                      href={l.href}
                      className={`relative rounded-full px-3 py-1.5 text-[13px] transition-colors duration-300 hover:text-foreground ${
                        isActive
                          ? "text-foreground font-medium"
                          : "text-foreground/70 hover:bg-white/[0.05]"
                      }`}
                    >
                      {l.label}
                      {isActive && (
                        <motion.span
                          layoutId="nav-active-pill"
                          className="absolute inset-0 -z-10 rounded-full bg-white/[0.08]"
                          transition={{ duration: 0.35, ease }}
                        />
                      )}
                    </a>
                  );
                })}
              </nav>

              <div className="flex items-center gap-2">
                <a
                  href={GITHUB_REPO_URL}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="hidden h-9 w-9 items-center justify-center rounded-full text-foreground/70 transition-colors duration-300 hover:bg-white/[0.05] hover:text-foreground md:flex"
                  aria-label="GitHub Repository"
                >
                  <Github className="h-4 w-4" />
                </a>

                <a href={CONSOLE_URL} className="btn-primary">
                  Get Started
                </a>

                <button
                  onClick={() => setMobileMenuOpen(true)}
                  className="flex h-9 w-9 items-center justify-center rounded-full text-foreground/75 transition-colors duration-300 hover:bg-white/[0.05] hover:text-foreground md:hidden"
                  aria-label="Open Menu"
                >
                  <Menu className="h-4 w-4" />
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Mobile Navigation Drawer */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="fixed inset-0 z-[100] flex flex-col bg-[#0b0c10]/98 backdrop-blur-2xl md:hidden"
          >
            {/* Header in Drawer */}
            <div className="flex h-20 items-center justify-between px-8">
              <a
                href="#top"
                onClick={() => setMobileMenuOpen(false)}
                className="font-display text-lg font-semibold tracking-tight text-foreground flex items-center gap-2"
              >
                <Logo className="h-5 w-5" />
                <span>Sentient</span>
              </a>
              <button
                onClick={() => setMobileMenuOpen(false)}
                className="p-2 text-foreground/70 transition-colors hover:text-foreground"
                aria-label="Close Menu"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Links */}
            <nav className="flex flex-1 flex-col items-center justify-center gap-8 px-6 text-center">
              {links.map((l, i) => {
                const isActive = activeSection === l.href.replace("#", "");
                return (
                  <motion.a
                    key={l.href}
                    href={l.href}
                    onClick={() => setMobileMenuOpen(false)}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.35, delay: 0.04 * i, ease }}
                    className={`relative text-2xl font-medium tracking-wide transition-colors ${
                      isActive
                        ? "text-foreground font-semibold"
                        : "text-foreground/80 hover:text-foreground"
                    }`}
                  >
                    {l.label}
                    {isActive && (
                      <motion.span
                        layoutId="nav-active-line"
                        className="absolute -left-5 top-1/2 h-1.5 w-1.5 -translate-y-1/2 rounded-full bg-brand"
                        transition={{ duration: 0.35, ease }}
                      />
                    )}
                  </motion.a>
                );
              })}

              <motion.a
                href={CONSOLE_URL}
                onClick={() => setMobileMenuOpen(false)}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.35, delay: 0.04 * (links.length + 1), ease }}
                className="btn-primary mt-6 w-full max-w-xs justify-center py-3 text-center text-sm"
              >
                Get Started
              </motion.a>
            </nav>

            {/* Footer inside drawer */}
            <div className="flex justify-center p-8 border-t border-white/[0.06]">
              <a
                href={GITHUB_REPO_URL}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
              >
                <Github className="h-4 w-4" />
                View on GitHub
              </a>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
