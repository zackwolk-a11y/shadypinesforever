#!/usr/bin/env bash
# Builds the single-file game and runs the automated checks.
set -e
cd "$(dirname "$0")/.."
node tools/build.js
node tests/reachability.js
node tests/mechanics.js
node tests/smoke.js > /tmp/smoke.log && grep -q "PAGE ERRORS: \[\]" /tmp/smoke.log && echo "SMOKE: no runtime errors in any level"
node tests/bosses.js
node tests/biker_boss.js
node tests/platform.js
