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

echo "→ cover frames"
for f in "$MEDIA"/*.mp4; do
  b="$(basename "$f" .mp4)"
  ffmpeg -y -loglevel error -ss 1.6 -i "$f" -frames:v 1 -q:v 2 "$MEDIA/$b-cover.jpg"
done

echo "✓ media rebuilt: $(ls "$MEDIA" | wc -l) files, $(du -sh "$MEDIA" | cut -f1)"
