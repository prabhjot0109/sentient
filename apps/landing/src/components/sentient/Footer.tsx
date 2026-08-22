import { Logo } from "./Logo";
import { GITHUB_REPO_URL } from "@/lib/site";

const cols = [
  {
    title: "Product",
    links: [
      { label: "Architecture", href: "#architecture" },
      { label: "How it works", href: "#how" },
      { label: "Games", href: "#games" },
      { label: "Platform", href: "#platform" },
    ],
  },
  {
    title: "Developers",
    links: [
      { label: "Documentation", href: "#docs" },
      { label: "API Reference", href: "#docs" },
      { label: "GitHub", href: GITHUB_REPO_URL },
      { label: "Changelog", href: "#" },
    ],
  },
  {
    title: "Community",
    links: [
      { label: "Discord", href: "https://discord.gg" },
      { label: "X / Twitter", href: "https://x.com" },
      { label: "Blog", href: "#" },
      { label: "License", href: "#" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="relative border-t border-border/60 pt-20 pb-10">
      <div className="mx-auto max-w-6xl px-6">
        <div className="grid gap-12 md:grid-cols-[1.4fr_1fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2">
              <Logo className="h-6 w-6" />
              <span className="font-semibold tracking-tight">Sentient</span>
            </div>
            <p className="mt-4 max-w-xs text-sm text-muted-foreground">
              The AI runtime for living game worlds. Bring every character to life.
            </p>
            <div className="mt-6 inline-flex items-center gap-2 rounded-full border border-border/60 bg-white/[0.03] px-3 py-1.5 text-xs text-muted-foreground">
              <span
                className="h-1.5 w-1.5 rounded-full"
                style={{ background: "oklch(0.75 0.15 150)" }}
              />
              All systems operational
            </div>
          </div>

          {cols.map((c) => (
            <div key={c.title}>
              <div className="text-xs uppercase tracking-widest text-muted-foreground">
                {c.title}
              </div>
              <ul className="mt-4 space-y-2 text-sm">
                {c.links.map((l) => {
                  const isExternal = l.href.startsWith("http");
                  return (
                    <li key={l.label}>
                      <a
                        href={l.href}
                        target={isExternal ? "_blank" : undefined}
                        rel={isExternal ? "noopener noreferrer" : undefined}
                        className="text-foreground/80 transition-colors hover:text-foreground"
                      >
                        {l.label}
                      </a>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-16 flex flex-col items-start justify-between gap-4 border-t border-border/60 pt-6 text-xs text-muted-foreground sm:flex-row sm:items-center">
          <p>© {new Date().getFullYear()} Sentient. Made with ♥ by Prabhjot Singh.</p>
          <p className="font-mono tracking-widest">v1.0.0 · api.sentient.dev</p>
        </div>
      </div>

      {/* Giant wordmark */}
      <div
        aria-hidden
        className="pointer-events-none mt-20 select-none overflow-hidden text-center leading-[0.8] tracking-[-0.05em]"
        style={{
          fontSize: "clamp(6rem, 22vw, 20rem)",
          fontWeight: 700,
          background: "linear-gradient(180deg, oklch(1 0 0 / 0.08), oklch(1 0 0 / 0))",
          WebkitBackgroundClip: "text",
          backgroundClip: "text",
          color: "transparent",
        }}
      >
        SENTIENT
      </div>
    </footer>
  );
}
