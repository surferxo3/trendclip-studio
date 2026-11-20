"""Command-line interface for TrendClip Studio."""

from __future__ import annotations

import argparse
import importlib.util
import os
import platform
import shutil
import sys
import tempfile
import json
from datetime import date
from pathlib import Path
from typing import List, Optional

from .config import ConfigError, load_topic, validate_date, validate_slug
from .discovery import DiscoveryError, discover_with_trends, save_report
from .paths import UnsafePathError, output_directory
from .render import RenderError, render_clip, write_metadata
from .validate import add_content_quality, inspect_media_quality, probe_video, write_validation


PROJECT_ROOT = Path(__file__).resolve().parent.parent
EXPORT_NAMES = ("clip-001.mp4", "clip-001.json", "validation.json")


def promote_export(staging: Path, destination: Path) -> None:
    """Promote a coherent staged export, restoring the prior set on any error."""
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".trendclip-backup-", dir=destination) as backup_value:
        backup = Path(backup_value)
        backed_up = []
        promoted = []
        try:
            for name in EXPORT_NAMES:
                target = destination / name
                if target.exists():
                    os.replace(target, backup / name)
                    backed_up.append(name)
            for name in EXPORT_NAMES:
                source = staging / name
                if not source.is_file():
                    raise RenderError(f"staged export is missing {name}")
                os.replace(source, destination / name)
                promoted.append(name)
        except (OSError, RenderError) as exc:
            for name in promoted:
                (destination / name).unlink(missing_ok=True)
            for name in backed_up:
                os.replace(backup / name, destination / name)
            raise RenderError(f"could not promote coherent export set: {exc}") from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="trendclip", description="TrendClip Studio video pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    render = subparsers.add_parser("render", help="render an original graphical short")
    render.add_argument("--topic", required=True, help="topic configuration slug")
    render.add_argument("--mode", default="original", choices=["original"])
    render.add_argument("--date", default=date.today().isoformat(), help="output date (YYYY-MM-DD)")
    render.add_argument("--output-root", type=Path, default=PROJECT_ROOT / "output")
    render.add_argument("--config-root", type=Path, default=PROJECT_ROOT / "config" / "topics")
    discovery = subparsers.add_parser("discover", help="rank candidates from approved read-only feeds")
    discovery.add_argument("--topic", required=True, help="topic configuration slug")
    dashboard = subparsers.add_parser("dashboard", help="run the local control dashboard")
    dashboard.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    dashboard.add_argument("--port", default=8765, type=int)
    studio = subparsers.add_parser("studio", help="refresh sources and open the local studio")
    studio.add_argument("--host", default="127.0.0.1", choices=["127.0.0.1", "localhost"])
    studio.add_argument("--port", default=8765, type=int)
    subparsers.add_parser("doctor", help="check local dependencies and installation health")
    production = subparsers.add_parser("produce-original", help="render a configured original animated production")
    production.add_argument(
        "--production",
        type=Path,
        default=PROJECT_ROOT / "productions" / "experiment-001-agentic-commerce",
    )
    benchmark = subparsers.add_parser("benchmark", help="score adjudicated creator-quality evidence")
    benchmark.add_argument("--manifest", type=Path, required=True)
    return parser


def _system_fix(name: str) -> str:
    system = platform.system().lower()
    if name in {"FFmpeg", "ffprobe"}:
        if system == "darwin":
            return "Install Homebrew, then run: brew install ffmpeg"
        if system == "windows":
            return "Run: winget install --id Gyan.FFmpeg -e, then open a new terminal"
        return "Ubuntu/Debian: sudo apt install ffmpeg (use your distribution package manager elsewhere)"
    if name == "Node.js":
        if system == "darwin":
            return "Install Homebrew, then run: brew install node"
        if system == "windows":
            return "Run: winget install OpenJS.NodeJS.LTS, then open a new terminal"
        return "Install the current Node.js LTS using your distribution package manager"
    if name == "Python 3.10+":
        return "Install Python 3.10 or newer from https://www.python.org/downloads/"
    if name == "Private environment":
        return "Run the TrendClip Setup launcher once before starting Studio"
    if name == "Project storage":
        return "Move TrendClip to a folder your user account can write to"
    return "Run the TrendClip Setup launcher again to repair Python packages"


def doctor_checks():
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    return [
        ("Python 3.10+", sys.version_info >= (3, 10), platform.python_version(), True),
        ("Private environment", in_venv, sys.prefix if in_venv else "not active", True),
        ("FFmpeg", shutil.which("ffmpeg") is not None, shutil.which("ffmpeg") or "not found", True),
        ("ffprobe", shutil.which("ffprobe") is not None, shutil.which("ffprobe") or "not found", True),
        ("Node.js", shutil.which("node") is not None, shutil.which("node") or "not found", True),
        ("yt-dlp", importlib.util.find_spec("yt_dlp") is not None, "Python package", True),
        ("Faster Whisper", importlib.util.find_spec("faster_whisper") is not None, "Python package; model downloads on first analysis", True),
        ("OpenCV", importlib.util.find_spec("cv2") is not None, "Python package", True),
        ("Project storage", os.access(PROJECT_ROOT, os.W_OK), str(PROJECT_ROOT), True),
        ("Codex assistance", shutil.which("codex") is not None, shutil.which("codex") or "optional; not installed", False),
    ]


def run_doctor() -> int:
    checks = doctor_checks()
    print("TrendClip Studio system check")
    for name, ready, detail, required in checks:
        state = "PASS" if ready else ("FAIL" if required else "INFO")
        print(f"  {state}  {name}: {detail}")
        if not ready and required:
            print(f"        Fix: {_system_fix(name)}")
    failed = [name for name, ready, _, required in checks if required and not ready]
    if failed:
        print("\nFix the failed requirements before starting Studio.")
        return 1
    print("\nYour system is ready. Codex is optional and never required.")
    return 0


def run_render(args: argparse.Namespace) -> int:
    topic = validate_slug(args.topic)
    output_date = validate_date(args.date)
    if any(shutil.which(tool) is None for tool in ("ffmpeg", "ffprobe")):
        raise RenderError("FFmpeg and ffprobe must be installed and available on PATH")
    config_root = args.config_root.resolve()
    try:
        config_root.relative_to(PROJECT_ROOT.resolve())
    except ValueError as exc:
        raise ConfigError("config root must remain inside the project") from exc
    config_file = (config_root / f"{topic}.json").resolve()
    try:
        config_file.relative_to(config_root)
    except ValueError as exc:
        raise ConfigError("configuration path escapes config root") from exc
    config = load_topic(config_file)
    if config.slug != topic:
        raise ConfigError("configuration slug does not match requested topic")
    if config.mode != args.mode:
        raise ConfigError(f"configuration does not support mode {args.mode!r}")

    destination = output_directory(PROJECT_ROOT, args.output_root, topic, output_date)
    destination.mkdir(parents=True, exist_ok=True)
    final_video = destination / "clip-001.mp4"
    with tempfile.TemporaryDirectory(prefix=".trendclip-stage-", dir=destination) as staging_value:
        staging = Path(staging_value)
        staged_video = staging / "clip-001.mp4"
        details = render_clip(config, staged_video)
        validation = add_content_quality(
            probe_video(staged_video, expected_fps=config.fps),
            inspect_media_quality(staged_video, allow_static=True, allow_silence=True),
        )
        if not validation["valid"]:
            print("Validation: FAILED (prior export preserved)")
            return 2
        write_validation(validation, staging / "validation.json")
        write_metadata(config, staging / "clip-001.json", final_video, details, validation)
        promote_export(staging, destination)
    print(f"Video: {final_video}")
    print(f"Validation: {'PASSED' if validation['valid'] else 'FAILED'}")
    return 0 if validation["valid"] else 2


def run_discover(args: argparse.Namespace) -> int:
    topic = validate_slug(args.topic)
    topic_config = load_topic(PROJECT_ROOT / "config" / "topics" / f"{topic}.json")
    report = discover_with_trends(topic_config, PROJECT_ROOT / "config" / "sources" / f"{topic}.json")
    destination = PROJECT_ROOT / "state" / "discovery" / topic / "latest.json"
    save_report(report, destination)
    print(f"Candidates: {report['candidate_count']}")
    print(f"Report: {destination}")
    if report["source_errors"]:
        print(f"Source errors: {len(report['source_errors'])}", file=sys.stderr)
        return 2
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            return run_doctor()
        if args.command == "render":
            return run_render(args)
        if args.command == "discover":
            return run_discover(args)
        if args.command == "produce-original":
            from .original_production import produce

            production = args.production.resolve()
            try:
                production.relative_to((PROJECT_ROOT / "productions").resolve())
            except ValueError as exc:
                raise ConfigError("production must remain inside the project productions directory") from exc
            report = produce(production)
            print(f"Video: {production / 'output' / 'final-video.mp4'}")
            print(f"Validation: {'PASSED' if report['validation']['valid'] else 'FAILED'}")
            return 0
        if args.command == "benchmark":
            from .benchmark import BenchmarkError, score_manifest

            try:
                report = score_manifest(args.manifest.resolve())
            except BenchmarkError as exc:
                print(f"error: {exc}", file=sys.stderr)
                return 1
            print(json.dumps(report, indent=2))
            return 0 if report["release_ready"] else 2
        if args.command in ("dashboard", "studio"):
            if not 1 <= args.port <= 65535:
                raise ConfigError("port must be between 1 and 65535")
            from .dashboard import serve_dashboard

            serve_dashboard(PROJECT_ROOT, args.host, args.port, open_browser=args.command == "studio")
            return 0
    except (ConfigError, UnsafePathError, RenderError, DiscoveryError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 1

