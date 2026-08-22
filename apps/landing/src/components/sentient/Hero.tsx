import { useEffect, useRef, useState } from "react";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "framer-motion";
import game1 from "@/assets/games/game-1.jpg";
import game2 from "@/assets/games/game-2.jpg";
import game3 from "@/assets/games/game-3.jpg";
import game4 from "@/assets/games/game-4.jpg";
import game5 from "@/assets/games/game-5.jpg";
import game6 from "@/assets/games/game-6.jpg";
import game7 from "@/assets/games/game-7.jpg";
import game8 from "@/assets/games/game-8.jpg";

/**
 * Clips are discovered from disk instead of imported by name.
 *
 * Vite resolves this at build time into content-hashed `/assets/<name>-<hash>.mp4`
 * URLs, which the deployed `_headers` rule already serves `immutable` — so a repeat
 * visitor never re-downloads them. When the directory holds no video (the state this
 * repo ships in), the glob is an empty object and every tile renders as a still. That
 * is the whole fallback mechanism: there is no error path to get wrong.
 *
 * To light a tile up: encode `game-N.mp4` (+ optional `game-N.webm`) into
 * `src/assets/games/` and flip `motion: true` on it below. See `README.md` there.
 */
const clipUrls = import.meta.glob("../../assets/games/*.{mp4,webm}", {
  eager: true,
  query: "?url",
  import: "default",
}) as Record<string, string>;

type Clip = { mp4?: string; webm?: string };

function findClip(name: string): Clip | undefined {
  const mp4 = clipUrls[`../../assets/games/${name}.mp4`];
  const webm = clipUrls[`../../assets/games/${name}.webm`];
  return mp4 || webm ? { mp4, webm } : undefined;
}

/**
 * Only four of the eight tiles are allowed to move.
 *
 * Eight simultaneously-playing clips behind a wordmark is noise, not cinema — the
 * eye has nowhere to rest and the title stops being the subject. These four are the
 * high-`depth` tiles below, so motion reinforces the depth hierarchy rather than
 * fighting it, and the four stills act as visual rest.
 */
const tiles = [
  { src: game1, name: "game-1", motion: false },
  { src: game2, name: "game-2", motion: true },
  { src: game3, name: "game-3", motion: false },
  { src: game4, name: "game-4", motion: true },
  { src: game5, name: "game-5", motion: true },
  { src: game6, name: "game-6", motion: false },
  { src: game7, name: "game-7", motion: false },
  { src: game8, name: "game-8", motion: true },
];

// Per-tile parallax depth (0 = static, 1 = full). Creates layered depth.
const depths = [0.35, 0.85, 0.5, 1.1, 0.95, 0.45, 0.7, 1.25];

const ease = [0.22, 1, 0.36, 1] as const;

// Spacing between decoder start-ups. Spinning four hardware decoders up in the same
// frame produces a visible hitch on mid-range laptops; staggered, it reads as intent.
const STAGGER_MS = 250;

type NetworkInformation = { saveData?: boolean; effectiveType?: string };

/**
 * Whether the hero may fetch and decode video at all.
 *
 * Resolved once after mount rather than on every render: a hero that starts as
 * stills should stay stills, not pop into motion mid-scroll. It is false during SSR
 * and on the first client paint, so no `<video>` element reaches the document until
 * every one of these gates has passed.
 */
function useVideoAllowed(reducedMotion: boolean): boolean {
  const [allowed, setAllowed] = useState(false);

  useEffect(() => {
    if (reducedMotion) return;
    // Below md the grid is 2-col and the tiles are thumbnails — not worth the bytes.
    if (!window.matchMedia("(min-width: 768px)").matches) return;

    const conn = (navigator as Navigator & { connection?: NetworkInformation }).connection;
    if (conn?.saveData) return;
    // Matches "2g" and "slow-2g" but not "3g"/"4g".
    if (conn?.effectiveType && /2g$/.test(conn.effectiveType)) return;

    setAllowed(true);
  }, [reducedMotion]);

  return allowed;
}

function ParallaxTile({
  src,
  clip,
  index,
  depth,
  mx,
  my,
  mounted,
  active,
  reduced,
}: {
  src: string;
  clip?: Clip;
  index: number;
  depth: number;
  mx: MotionValue<number>;
  my: MotionValue<number>;
  mounted: boolean;
  active: boolean;
  reduced: boolean;
}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  // Flipped by `canplay`, which cross-fades the clip over its own poster. If the file
  // 404s, the codec is unsupported, or autoplay is refused, this simply never fires.
  const [ready, setReady] = useState(false);

  // Each tile transforms the shared, spring-smoothed pointer signal by its own depth.
  const x = useTransform(mx, (v) => -v * 80 * depth);
  const y = useTransform(my, (v) => -v * 80 * depth);
  const rotate = useTransform(mx, (v) => -v * 1.4 * depth);

  useEffect(() => {
    const el = videoRef.current;
    if (!el) return;

    if (!active) {
      el.pause();
      return;
    }

    let cancelled = false;
    const timer = window.setTimeout(() => {
      if (cancelled) return;
      // `preload="none"` means this call is what starts the download.
      void el.play().catch(() => {
        // Autoplay refused. The poster underneath is already the fallback.
      });
    }, index * STAGGER_MS);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [active, index]);

  const media = "h-full w-full object-cover contrast-[1.05] saturate-[1.05]";
  const scale = { transform: `scale(${1 + depth * 0.08})` };
  const rest = { opacity: 1, y: 0, filter: "blur(0px)" };
  const hidden = { opacity: 0, y: 40, filter: "blur(12px)" };

  return (
    <motion.div
      initial={reduced ? rest : hidden}
      animate={mounted || reduced ? rest : hidden}
      transition={reduced ? { duration: 0 } : { duration: 1.4, ease, delay: 0.05 * index }}
      style={reduced ? undefined : { x, y, rotate }}
      className="relative aspect-[3/4] overflow-hidden rounded-[2px] will-change-transform"
    >
      <img
        src={src}
        alt=""
        loading={index < 4 ? "eager" : "lazy"}
        width={768}
        height={1024}
        className={`${media} opacity-90`}
        style={scale}
      />

      {clip && (
        <video
          ref={videoRef}
          poster={src}
          muted
          loop
          playsInline
          preload="none"
          disablePictureInPicture
          disableRemotePlayback
          tabIndex={-1}
          aria-hidden
          onCanPlay={() => setReady(true)}
          onError={() => setReady(false)}
          className={`${media} absolute inset-0 transition-opacity duration-700 ${
            ready ? "opacity-90" : "opacity-0"
          }`}
          style={scale}
        >
          {clip.webm && <source src={clip.webm} type="video/webm" />}
          {clip.mp4 && <source src={clip.mp4} type="video/mp4" />}
        </video>
      )}
    </motion.div>
  );
}

export function Hero() {
  const containerRef = useRef<HTMLElement>(null);
  const [mounted, setMounted] = useState(false);

  const reduced = useReducedMotion() ?? false;
  const videoAllowed = useVideoAllowed(reduced);

  // Video runs only while the hero is actually on screen in a foreground tab. The
  // section is h-[100svh], so it leaves the viewport almost immediately — without
  // this, four streams would keep decoding for the entire rest of the page.
  const [inView, setInView] = useState(true);
  const [pageVisible, setPageVisible] = useState(true);
  const active = videoAllowed && inView && pageVisible;

  useEffect(() => setMounted(true), []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el || typeof IntersectionObserver === "undefined") return;
    const io = new IntersectionObserver(([entry]) => setInView(entry.isIntersecting), {
      threshold: 0.05,
    });
    io.observe(el);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    const onVisibility = () => setPageVisible(document.visibilityState === "visible");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

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
    if (reduced || !containerRef.current) return;
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
        style={reduced ? undefined : { scale: gridScale, opacity: gridOpacity }}
        className="absolute inset-0 flex items-center justify-center"
      >
        <div className="grid w-full max-w-[96rem] grid-cols-2 gap-4 p-6 sm:gap-6 sm:p-10 md:grid-cols-4 md:gap-8 md:p-14">
          {tiles.map((tile, i) => (
            <ParallaxTile
              key={tile.name}
              src={tile.src}
              clip={tile.motion && videoAllowed ? findClip(tile.name) : undefined}
              index={i}
              depth={depths[i] ?? 0.5}
              mx={mx}
              my={my}
              mounted={mounted}
              active={active}
              reduced={reduced}
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
          style={reduced ? undefined : { y: wordmarkY, opacity: wordmarkOpacity }}
          className="pointer-events-none flex select-none flex-col items-center text-foreground"
        >
          <h1
            className="cursor-default text-center font-display font-semibold leading-[0.88] tracking-[-0.055em] text-foreground"
            style={{ fontSize: "clamp(3.5rem, 14vw, 10rem)" }}
          >
            {/* The animated version is one span per letter, which screen readers spell
                out. Give them the word, and hide the decorative copy from the tree. */}
            <span className="sr-only">Sentient</span>
            <span aria-hidden>
              {reduced
                ? "Sentient"
                : "Sentient".split("").map((c, i) => (
                    <motion.span
                      key={i}
                      initial={{ opacity: 0, y: 40, filter: "blur(12px)" }}
                      animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                      transition={{ duration: 1.2, ease, delay: 0.35 + i * 0.05 }}
                      className="inline-block"
                    >
                      {c}
                    </motion.span>
                  ))}
            </span>
          </h1>
        </motion.div>
      </div>

      {/* Bottom-center bio */}
      <motion.div
        initial={reduced ? { opacity: 1, y: 0 } : { opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={reduced ? { duration: 0 } : { duration: 1.2, ease, delay: 1.1 }}
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
