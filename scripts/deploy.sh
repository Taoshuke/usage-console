#!/usr/bin/env bash
# Collects fresh usage, rebuilds the page and deploys it with wrangler (macOS / Linux).
# For unattended runs, export CLOUDFLARE_API_TOKEN (Workers Scripts: Edit) in the environment.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 collector/collect.py
python3 scripts/build.py
CI=1 npx --no-install wrangler deploy
