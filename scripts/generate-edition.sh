#!/usr/bin/env bash
# scripts/generate-edition.sh
# Run the full generation pipeline for today's edition.
set -euo pipefail

DATE="${1:-$(date +%Y-%m-%d)}"
EDITION_TYPE="${2:-}"

echo "Generating MLB Daily Sports Page for ${DATE}..."

if [ -n "$EDITION_TYPE" ]; then
  daily-sports-page run --date "$DATE" --edition-type "$EDITION_TYPE" --publish
else
  daily-sports-page run --date "$DATE" --publish
fi

echo "Done."
