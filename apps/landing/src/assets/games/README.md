# Hero tile media

The hero grid in `src/components/sentient/Hero.tsx` is eight 3:4 tiles. Every tile has a
poster (`game-N.jpg`). Four of them can additionally play a looping clip.

## Adding a clip

1. Encode it:

   ```bash
   ./scripts/encode-hero-clip.sh <source-video> game-2 <start-seconds> <duration>
   ```

   That writes `game-2.mp4`, `game-2.webm`, and re-derives `game-2.jpg` from frame 0 of
   the encode.

2. That is the whole step. `Hero.tsx` discovers files here with `import.meta.glob`, so a
   tile marked `motion: true` lights up on the next build and needs no code change. A
   tile with no matching file stays a still — the glob is simply empty for it.

To move motion onto a *different* tile, flip `motion` in the `tiles` array in `Hero.tsx`.

## Which four, and why only four

`motion: true` is set on `game-2`, `game-4`, `game-5`, `game-8` — the four highest values
in the `depths` array. Motion on the tiles that already travel most under the pointer
reinforces the depth hierarchy; the four stills are visual rest.

Do not raise this to eight. Eight clips moving behind the wordmark is noise — the eye has
nowhere to settle and the title stops being the subject. Six is the ceiling.

## What makes a good source clip

- **4–6 seconds, seamlessly loopable.** Match the first and last frame, or ping-pong it.
  A visible loop seam is the single most amateur-looking failure mode here.
- **Slow camera drift only** — a pan, torch flicker, snowfall, rain on neon. Fast action
  fights the parallax and eats bitrate for detail nobody can resolve at 332px.
- **No HUD, no subtitles, no UI.** These are mood plates, not gameplay capture.
- **Dark and desaturated toward the edges.** They sit under a radial vignette; a bright
  clip punches through it and steals attention from the wordmark.

## Budget

Keep the four clips **under ~3MB combined**. The current poster set is 796KB. A page whose
entire pitch is low latency should not open with a 25MB download.

## Playback rules already handled in `Hero.tsx`

No clip is fetched at all when any of these hold — do not re-litigate them in a component:

| Gate | Reason |
| --- | --- |
| `prefers-reduced-motion` | Accessibility |
| Viewport < 768px | Grid is 2-col there; tiles are thumbnails |
| `navigator.connection.saveData` | Explicit user request |
| `effectiveType` matches `2g$` | Slow network |

Beyond that, playback is staggered 250ms per tile so four hardware decoders do not start
in one frame, and pauses when the hero scrolls out of view or the tab goes to background.

## Unused posters

`skyrim-dragon.jpg` and `cyberpunk-city.jpg` are not imported by any component, so they
are not bundled and cost nothing. They are kept as candidate art.
