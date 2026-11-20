#!/bin/zsh

set -e

PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

if [[ ! -x "$PROJECT_DIR/.venv/bin/python" ]]; then
  echo "TrendClip needs its one-time setup. Double-click Setup TrendClip Studio.command first."
  read -k 1 "?Press any key to close."
  exit 1
fi

if curl -fsS "http://127.0.0.1:8765/api/status" >/dev/null 2>&1; then
  open "http://127.0.0.1:8765"
  exit 0
fi

exec "$PROJECT_DIR/.venv/bin/python" -m trendclip studio
