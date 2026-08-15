import { createFileRoute } from "@tanstack/react-router";
import { Nav } from "@/components/sentient/Nav";
import { Hero } from "@/components/sentient/Hero";
import { Problem } from "@/components/sentient/Problem";
import { Architecture } from "@/components/sentient/Architecture";
import { HowItWorks } from "@/components/sentient/HowItWorks";
import { Games } from "@/components/sentient/Games";
import { Features } from "@/components/sentient/Features";
import { CodeExample } from "@/components/sentient/CodeExample";
import { Performance } from "@/components/sentient/Performance";
import { Vision } from "@/components/sentient/Vision";
import { Footer } from "@/components/sentient/Footer";
import { AmbientBackground } from "@/components/sentient/AmbientBackground";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Sentient — AI NPCs With Memory, Lore and Voice" },
      {
        name: "description",
        content:
          "Sentient is the AI runtime for living game worlds: give any NPC persistent memory, lore-grounded retrieval and a voice across every game you ship.",
      },
      { property: "og:title", content: "Sentient — AI NPCs With Memory, Lore and Voice" },
      {
        property: "og:description",
        content:
          "One runtime, every game. Build lore-aware NPCs with memory, RAG and streaming APIs — production-ready from day one.",
      },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Landing,
});

function Seam() {
  return (
    <div aria-hidden className="mx-auto max-w-6xl px-6">
      <div className="section-seam" />
    </div>
  );
}

function Landing() {
  return (
    <div className="relative min-h-screen overflow-x-clip bg-background text-foreground">
      <AmbientBackground />
      <Nav />
      <main>
        <Hero />
        <Problem />
        <Seam />
        <Architecture />
        <Seam />
        <HowItWorks />
        <Seam />
        <Games />
        <Seam />
        <Features />
        <Seam />
        <CodeExample />
        <Seam />
        <Performance />
        <Vision />
      </main>
      <Footer />
    </div>
  );
}
