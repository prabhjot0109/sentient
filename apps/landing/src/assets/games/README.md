# Hero tile media

The hero grid in `src/components/sentient/Hero.tsx` is eight 3:4 tiles, each carrying a
poster (`game-N.jpg`) and, once encoded, a looping clip (`game-N.mp4` / `.webm`).

## Adding a clip

1. Encode it:

   ```bash
   ./scripts/encode-hero-clip.sh <source-video> game-2 <start-seconds> <duration>
   ```

   That writes `game-2.mp4`, `game-2.webm`, and re-derives `game-2.jpg` from frame 0 of
   the encode.

2. That is the whole step. `Hero.tsx` discovers files here with `import.meta.glob`, so
   the matching tile lights up on the next build with no code change. A tile with no
   matching file just stays a still — the glob is simply empty for it, which is also
   the state this repo ships in until clips exist for all eight.

All eight tiles are marked `motion: true` in `Hero.tsx`; encode the ones you have footage
for and leave the rest — there is no per-tile toggle to flip.

## What makes a good source clip

- **4–6 seconds, seamlessly loopable.** Match the first and last frame, or ping-pong it.
  A visible loop seam is the single most amateur-looking failure mode here.
- **Slow camera drift only** — a pan, torch flicker, snowfall, rain on neon. Fast action
  fights the parallax and eats bitrate for detail nobody can resolve at 332px.
- **No HUD, no subtitles, no UI.** These are mood plates, not gameplay capture.
- **Dark and desaturated toward the edges.** They sit under a radial vignette; a bright
  clip punches through it and steals attention from the wordmark.

## Budget

Keep all eight clips **under ~6MB combined** — roughly 700KB each. The current poster set
is 796KB; a page whose entire pitch is low latency should not open with a 40MB download.
If you go over, raise `-crf` (27 → 30) or shorten the clip before you raise resolution.

Note that all eight autoplaying at once is heavier than the original 4-tile design (more
bandwidth on first load, more concurrent hardware decoders). The gates below exist
specifically to keep that cost off mobile, slow connections, and reduced-motion visitors —
they're doing more work now than when only half the grid moved.

## Playback rules already handled in `Hero.tsx`

No clip is fetched at all when any of these hold — do not re-litigate them in a component:

| Gate                            | Reason                                    |
| ------------------------------- | ----------------------------------------- |
| `prefers-reduced-motion`        | Accessibility                             |
| Viewport < 768px                | Grid is 2-col there; tiles are thumbnails |
| `navigator.connection.saveData` | Explicit user request                     |
| `effectiveType` matches `2g$`   | Slow network                              |

Beyond that, playback is staggered 220ms per tile so eight hardware decoders do not start
in one frame (last tile begins ~1.5s after the first), and pauses when the hero scrolls
out of view or the tab goes to background.

## Unused posters

`skyrim-dragon.jpg` and `cyberpunk-city.jpg` are not imported by any component, so they
are not bundled and cost nothing. They are kept as candidate art.
