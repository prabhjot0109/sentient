#!/usr/bin/env bash
#
# Encode one hero tile clip for src/assets/games/.
#
# Usage:
#   ./scripts/encode-hero-clip.sh <source-video> <game-N> [start-seconds] [duration]
#
# Example:
#   ./scripts/encode-hero-clip.sh ~/captures/skyrim-dusk.mkv game-2 41 6
#
# Produces, next to the existing posters:
#   src/assets/games/<game-N>.mp4    H.264, universal
#   src/assets/games/<game-N>.webm   VP9, ~30-40% smaller where supported
#   src/assets/games/<game-N>.jpg    poster, extracted from frame 0 of the mp4
#
# Runs in Git Bash on Windows. Requires ffmpeg on PATH.

set -euo pipefail

SRC=${1:?usage: encode-hero-clip.sh <source-video> <game-N> [start] [duration]}
NAME=${2:?missing output name, e.g. game-2}
START=${3:-0}
DURATION=${4:-6}

OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)/src/assets/games"

# Tiles render at ~332px wide (1536px grid, 4 cols, gap-8, p-14), scaled up to 1.1
# by the depth transform, so ~365 CSS px => ~730px at DPR 2. Encoding above that is
# bytes thrown away, especially under a vignette, 90% opacity and a grain overlay.
WIDTH=540
HEIGHT=720
FPS=24

# Largest centred 3:4 region, then down to target. Handles any source aspect.
CROP="crop='min(iw\,ih*3/4)':'min(ih\,iw*4/3)'"
VF="${CROP},scale=${WIDTH}:${HEIGHT}:flags=lanczos,fps=${FPS}"

echo "==> ${NAME}: ${DURATION}s from ${START}s of $(basename "$SRC")"

# -an: no audio track. Saves bytes and removes any chance of an autoplay block.
# +faststart: moov atom at the front so playback can begin before the full download.
ffmpeg -hide_banner -loglevel error -y \
  -ss "$START" -i "$SRC" -t "$DURATION" \
  -vf "$VF" \
  -c:v libx264 -profile:v high -crf 27 -preset slow \
  -pix_fmt yuv420p -movflags +faststart -an \
  "${OUT_DIR}/${NAME}.mp4"

ffmpeg -hide_banner -loglevel error -y \
  -i "${OUT_DIR}/${NAME}.mp4" \
  -c:v libvpx-vp9 -crf 34 -b:v 0 -row-mt 1 -an \
  "${OUT_DIR}/${NAME}.webm"

# The poster MUST come from the encoded clip, not the source. If it does not match
# frame 0 exactly you get a visible jump-cut the moment the video fades in.
ffmpeg -hide_banner -loglevel error -y \
  -i "${OUT_DIR}/${NAME}.mp4" -frames:v 1 -q:v 3 \
  "${OUT_DIR}/${NAME}.jpg"

echo "==> written:"
ls -lh "${OUT_DIR}/${NAME}".{mp4,webm,jpg} | awk '{printf "    %-8s %s\n", $5, $9}'
echo
echo "    Budget check: keep all eight clips under ~6MB combined (~700KB each)."
echo "    Too big? Raise -crf (27 -> 30) or shorten the clip before raising resolution."
