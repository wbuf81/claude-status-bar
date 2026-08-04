#!/bin/bash
# Headless check of the Daisy state machine — no hooks, no menu bar takeover.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p build
swiftc -O Sources/DaisyFrames.swift Sources/DaisyRender.swift Sources/DaisyState.swift \
  tools/DriverTest.swift -o build/DriverTest -framework Cocoa
exec build/DriverTest
