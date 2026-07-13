#!/usr/bin/env bash
# scripts/publish-edition.sh
# Publish a pre-built edition from the build directory.
set -euo pipefail

BUILD_DIR="${1:-build}"

echo "Publishing from ${BUILD_DIR}..."
daily-sports-page publish "$BUILD_DIR"
echo "Published."
