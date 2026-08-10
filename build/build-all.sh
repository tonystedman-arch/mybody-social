#!/usr/bin/env bash
# Rebuild every piece of media the poster serves, from source.
#   ./build/build-all.sh
# Outputs straight into media/, which is what MEDIA_BASE_URL points at.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/.." && pwd)"
MEDIA="$REPO/media"
mkdir -p "$MEDIA"

echo "→ fonts"
npm --prefix /tmp install geist --silent --no-audit --no-fund

echo "→ end cards"
CARDS_OUT="$MEDIA" python3 "$HERE/render-pro-launch-v2.py"

echo "→ reels"
RAW_DIR="$HERE/raw" CARDS_DIR="$MEDIA" OUT_DIR="$MEDIA" REELS_SPEC="$HERE/reels.json" \
  python3 "$HERE/build_reels.py"

echo "→ the receipt"
# Built by its own script, not build_reels.py: it is an artefact rather than a
# screen tour, so it has no device layer and its own timing.
OUT_DIR="$MEDIA" python3 "$HERE/build_receipt.py"

echo "→ cover frames"
for f in "$MEDIA"/*.mp4; do
  b="$(basename "$f" .mp4)"
  # The receipt's own cover is taken later in the clip, once the rows have
  # arrived — 1.6s would catch it mid-reveal with half the numbers missing.
  if [ "$(basename "$f")" = "receipt.mp4" ]; then ss=4.0; else ss=1.6; fi
  ffmpeg -y -loglevel error -ss "$ss" -i "$f" -frames:v 1 -q:v 2 "$MEDIA/$b-cover.jpg"
done

echo "✓ media rebuilt: $(ls "$MEDIA" | wc -l) files, $(du -sh "$MEDIA" | cut -f1)"
