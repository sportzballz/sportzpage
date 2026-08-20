#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_ROOT="${SPORTZBALLZ_SITE_ROOT:-/Users/asmith/.openclaw/workspace/sportzballz.io}"
EDITION_DATE="${SPORTZPAGE_EDITION_DATE:-$(TZ=America/New_York date -v-1d +%F)}"

cd "$ROOT"
echo "Generating The Daily Sportz Page for ${EDITION_DATE}"
"$ROOT/.venv/bin/daily-sports-page" run \
  --date "$EDITION_DATE" \
  --build-dir "$ROOT/build"

mkdir -p "$SITE_ROOT/sportzpage/static"
cp "$ROOT/build/index.html" "$ROOT/build/edition.json" "$SITE_ROOT/sportzpage/"
cp -R "$ROOT/static/css" "$ROOT/static/js" "$SITE_ROOT/sportzpage/static/"

SPORTZBALLZ_SITE_ROOT="$SITE_ROOT" \
  /Users/asmith/.openclaw/workspace/baseball-llm/scripts/publish-site.sh

echo "SportzPage generation and site publication complete for ${EDITION_DATE}"
