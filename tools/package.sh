#!/usr/bin/env bash
# Package the plugin for Claude: dist/creative-studio.plugin
# Includes only what the plugin needs at runtime. Dev files (tests, tools, jobs) stay out.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="$(python3 -c "import json;print(json.load(open('$ROOT/.claude-plugin/plugin.json'))['name'])")"
VERSION="$(python3 -c "import json;print(json.load(open('$ROOT/.claude-plugin/plugin.json'))['version'])")"
OUT="$ROOT/dist"
mkdir -p "$OUT"
rm -f "$OUT/$NAME.plugin"
cd "$ROOT"
python3 -m pytest tests -q
zip -qr "$OUT/$NAME.plugin" .claude-plugin agents skills hooks README.md \
  -x "*/__pycache__/*" "*.pyc" "*.DS_Store"
echo "$OUT/$NAME.plugin ($NAME $VERSION)"
unzip -l "$OUT/$NAME.plugin" | tail -1
