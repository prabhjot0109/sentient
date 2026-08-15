import { useEffect, useRef, useState } from "react";
import { motion, useMotionValue, useScroll, useSpring, useTransform } from "framer-motion";
import game1 from "@/assets/games/game-1.jpg";
import game2 from "@/assets/games/game-2.jpg";
import game3 from "@/assets/games/game-3.jpg";
import game4 from "@/assets/games/game-4.jpg";
import game5 from "@/assets/games/game-5.jpg";
import game6 from "@/assets/games/game-6.jpg";
import game7 from "@/assets/games/game-7.jpg";
import game8 from "@/assets/games/game-8.jpg";
import clip1 from "@/assets/games/game-1.mp4.asset.json";
import clip2 from "@/assets/games/game-2.mp4.asset.json";
import clip3 from "@/assets/games/game-3.mp4.asset.json";
import clip4 from "@/assets/games/game-4.mp4.asset.json";
import clip5 from "@/assets/games/game-5.mp4.asset.json";
import clip6 from "@/assets/games/game-6.mp4.asset.json";
import clip7 from "@/assets/games/game-7.mp4.asset.json";
import clip8 from "@/assets/games/game-8.mp4.asset.json";

const tiles: { src: string; video?: string }[] = [
  { src: game1, video: clip1.url },
  { src: game2, video: clip2.url },
  { src: game3, video: clip3.url },
  { src: game4, video: clip4.url },
  { src: game5, video: clip5.url },
  { src: game6, video: clip6.url },
  { src: game7, video: clip7.url },
  { src: game8, video: clip8.url },
];

// Per-tile parallax depth (0 = static, 1 = full). Creates layered depth.
const depths = [0.35, 0.85, 0.5, 1.1, 0.95, 0.45, 0.7, 1.25];

const ease = [0.22, 1, 0.36, 1] as const;

function ParallaxTile({
  src,
  video,
  index,
  depth,
  mx,
  my,
  mounted,
}: {
  src: string;
  video?: string;
  index: number;
  depth: number;
  mx: ReturnType<typeof useMotionValue<number>>;
  my: ReturnType<typeof useMotionValue<number>>;
  mounted: boolean;
}) {
  // Each tile transforms the shared, spring-smoothed pointer signal by its own depth.
  const x = useTransform(mx, (v) => -v * 80 * depth);
  const y = useTransform(my, (v) => -v * 80 * depth);
  const rotate = useTransform(mx, (v) => -v * 1.4 * depth);

  const media = "h-full w-full object-cover opacity-90 contrast-[1.05] saturate-[1.05]";
  const scale = { transform: `scale(${1 + depth * 0.08})` };

  return (
    <motion.div
      initial={{ opacity: 0, y: 40, filter: "blur(12px)" }}
      animate={
        mounted
          ? { opacity: 1, y: 0, filter: "blur(0px)" }
          : { opacity: 0, y: 40, filter: "blur(12px)" }
      }
      transition={{ duration: 1.4, ease, delay: 0.05 * index }}
      style={{ x, y, rotate }}
      className="aspect-[3/4] overflow-hidden rounded-[2px] will-change-transform"
    >
      {video ? (
        <video
          src={video}
          poster={src}
          autoPlay
          muted
          loop
          playsInline
          preload="metadata"
          aria-hidden
          className={media}
          style={scale}
        />
      ) : (
        <img
          src={src}
          alt=""
          loading={index < 4 ? "eager" : "lazy"}
          width={768}
          height={1024}
          className={media}
          style={scale}
        />
      )}
    </motion.div>
  );
}

export function Hero() {
  const containerRef = useRef<HTMLElement>(null);
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  // Raw pointer signal, then a spring for silky-smooth follow.
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const mx = useSpring(rawX, { stiffness: 80, damping: 20, mass: 0.6 });
  const my = useSpring(rawY, { stiffness: 80, damping: 20, mass: 0.6 });

  const { scrollY } = useScroll();
  const wordmarkY = useTransform(scrollY, [0, 600], [0, -80]);
  const wordmarkOpacity = useTransform(scrollY, [0, 400], [1, 0]);
  const gridScale = useTransform(scrollY, [0, 600], [1, 1.08]);
  const gridOpacity = useTransform(scrollY, [0, 600], [1, 0.35]);

  const handleMouseMove = (e: React.MouseEvent) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    rawX.set((e.clientX - rect.left - rect.width / 2) / (rect.width / 2));
    rawY.set((e.clientY - rect.top - rect.height / 2) / (rect.height / 2));
  };

  const handleLeave = () => {
    rawX.set(0);
    rawY.set(0);
  };

  return (
    <section
      ref={containerRef}
      id="top"
      onMouseMove={handleMouseMove}
      onMouseLeave={handleLeave}
      className="relative h-[100svh] w-full overflow-hidden"
    >
      {/* Parallax image grid with per-tile depth */}
      <motion.div
        style={{ scale: gridScale, opacity: gridOpacity }}
        className="absolute inset-0 flex items-center justify-center"
      >
        <div className="grid w-full max-w-[96rem] grid-cols-2 gap-4 p-6 sm:gap-6 sm:p-10 md:grid-cols-4 md:gap-8 md:p-14">
          {tiles.map((tile, i) => (
            <ParallaxTile
              key={i}
              src={tile.src}
              video={tile.video}
              index={i}
              depth={depths[i] ?? 0.5}
              mx={mx}
              my={my}
              mounted={mounted}
            />
          ))}
        </div>
      </motion.div>

      {/* Cinematic vignette + edge fade */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 h-full w-full"
        style={{
          background:
            "radial-gradient(ellipse at center, transparent 30%, oklch(0.055 0.004 260 / 0.85) 100%)",
        }}
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 bottom-0 h-40"
        style={{
          background: "linear-gradient(180deg, transparent, oklch(0.055 0.004 260))",
        }}
      />
      {/* Film grain overlay */}
      <div aria-hidden className="grain-overlay" />

      {/* Centered wordmark with scroll parallax */}
      <div className="pointer-events-none absolute inset-0 z-10 flex flex-col items-center justify-center px-6">
        <motion.div
          style={{ y: wordmarkY, opacity: wordmarkOpacity }}
          className="pointer-events-none flex select-none flex-col items-center text-foreground"
        >
          <h1 className="cursor-default text-center font-display font-semibold leading-[0.88] tracking-[-0.055em] text-foreground">
            {"Sentient".split("").map((c, i) => (
              <motion.span
                key={i}
                initial={{ opacity: 0, y: 40, filter: "blur(12px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                transition={{
                  duration: 1.2,
                  ease,
                  delay: 0.35 + i * 0.05,
                }}
                className="inline-block"
                style={{ fontSize: "clamp(3.5rem, 14vw, 10rem)" }}
              >
                {c}
              </motion.span>
            ))}
          </h1>
        </motion.div>
      </div>

      {/* Bottom-center bio */}
      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1.2, ease, delay: 1.1 }}
        className="absolute inset-x-0 bottom-10 z-10 flex justify-center px-6 md:bottom-14"
      >
        <p className="max-w-3xl text-center text-sm leading-relaxed text-foreground/75 md:text-base">
          An AI runtime for living game worlds. Give any NPC memory, lore, and a voice — one
          platform, every game, every character.
        </p>
      </motion.div>
    </section>
  );
}
