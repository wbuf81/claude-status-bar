#!/bin/bash
# Build and run the Daisy animation debug viewer.
#
#   ./tools/preview.sh
#
# Compiles the real DaisyFrames.swift + DaisyRender.swift together with the standalone viewer, so
# the window shows exactly what the menu bar will. Deliberately does NOT compile main.swift - the
# viewer has its own entry point and the app would fight it for one.
set -euo pipefail
cd "$(dirname "$0")/.."

BIN=build/DaisyPreview
mkdir -p build art/preview

echo "Compiling preview…"
swiftc -O \
  Sources/DaisyFrames.swift \
  Sources/DaisyRender.swift \
  tools/DaisyPreview.swift \
  -o "$BIN" \
  -framework Cocoa

echo "Running (space = pause, arrows = step, G = grid, S = save contact sheet)"
exec "$BIN"
