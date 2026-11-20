#!/usr/bin/env sh
set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
  printf '%s\n' "TrendClip needs its one-time setup. Run: ./setup-trendclip.sh"
  exit 1
fi

exec "$PROJECT_DIR/.venv/bin/python" -m trendclip studio
