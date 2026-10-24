#!/usr/bin/env bash
# Collects fresh usage and writes it to Notion (storage "notion"); no deploy needed. Needs NOTION_TOKEN.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 collector/collect.py
