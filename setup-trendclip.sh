#!/usr/bin/env sh

set -eu

PROJECT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$PROJECT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  printf '%s\n' "Python 3.10 or newer is required: https://www.python.org/downloads/"
  exit 1
fi

if ! "$PYTHON" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)'; then
  printf '%s\n' "Python 3.10 or newer is required."
  exit 1
fi

if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
  printf '%s\n' "FFmpeg and ffprobe are required before setup can finish."
  case "$(uname -s)" in
    Darwin) printf '%s\n' "Install Homebrew, then run: brew install ffmpeg" ;;
    *) printf '%s\n' "Ubuntu/Debian: sudo apt install ffmpeg" \
         "Use your distribution package manager on other Linux systems." ;;
  esac
  exit 1
fi

if ! command -v node >/dev/null 2>&1; then
  printf '%s\n' "Node.js LTS is required for reliable YouTube access."
  case "$(uname -s)" in
    Darwin) printf '%s\n' "Install Homebrew, then run: brew install node" ;;
    *) printf '%s\n' "Install the current Node.js LTS using your distribution package manager." ;;
  esac
  exit 1
fi

if [ ! -x "$PROJECT_DIR/.venv/bin/python" ]; then
  "$PYTHON" -m venv "$PROJECT_DIR/.venv"
fi

"$PROJECT_DIR/.venv/bin/python" -m pip install --upgrade pip setuptools wheel
"$PROJECT_DIR/.venv/bin/python" -m pip install -e "$PROJECT_DIR"
"$PROJECT_DIR/.venv/bin/python" -m trendclip doctor

printf '\n%s\n' "Setup complete. Start TrendClip Studio with the launcher for your operating system."
