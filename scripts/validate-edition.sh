#!/usr/bin/env bash
# scripts/validate-edition.sh
# Validate an Edition JSON file.
set -euo pipefail

EDITION_JSON="${1:-build/edition.json}"

echo "Validating ${EDITION_JSON}..."
daily-sports-page validate "$EDITION_JSON" --strict
echo "Validation passed."
