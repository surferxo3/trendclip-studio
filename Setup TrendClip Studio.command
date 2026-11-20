#!/bin/zsh

set -e

PROJECT_DIR="${0:A:h}"
cd "$PROJECT_DIR"

if "$PROJECT_DIR/setup-trendclip.sh"; then
  echo
  read -k 1 "?Setup complete. Press any key to close."
else
  echo
  read -k 1 "?Setup could not finish. Follow the instruction above, then try again. Press any key to close."
  exit 1
fi
