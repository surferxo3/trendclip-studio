#!/usr/bin/env python3
"""Reproducible local end-to-end smoke test using synthetic authorized media."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from trendclip.media_pipeline import _write_json, render_candidate_clip


def _generate_source(path: Path) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-v",
        "error",
        "-f",
        "lavfi",
        "-i",
        "testsrc2=size=1280x720:rate=30:duration=12",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=660:sample_rate=48000:duration=12",
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-shortest",
        str(path),
    ]
    subprocess.run(command, check=True, capture_output=True)


def run() -> dict:
    with tempfile.TemporaryDirectory(prefix="trendclip-source-smoke-") as directory:
        root = Path(directory)
        job_id = "0123456789ab"
        job = root / "state" / "jobs" / job_id
        job.mkdir(parents=True)
        source = job / "source.mp4"
        _generate_source(source)
        now = datetime.now(timezone.utc).isoformat()
        rights = {
            "category": "creator-owned",
            "permission_reference": "Synthetic test source generated locally",
            "allowed_platforms": ["facebook", "tiktok", "youtube"],
            "commercial_use_scope": "commercial",
            "attribution_required": False,
            "attribution_note": "",
            "confirmed_at": now,
        }
        info = {
            "job_id": job_id,
            "title": "Synthetic GTA-style motion test",
            "channel": "TrendClip Studio test fixture",
            "source_url": "https://www.youtube.com/watch?v=synthetic-test-only",
            "duration": 12.0,
            "downloaded_at": now,
            "rights": rights,
            "authentication": "synthetic-local",
        }
        words = [
            {"w": "WAIT", "s": 0.4, "e": 0.9},
            {"w": "LOOK", "s": 1.0, "e": 1.5},
            {"w": "AT", "s": 1.6, "e": 1.9},
            {"w": "THIS", "s": 2.0, "e": 2.5},
            {"w": "CHASE", "s": 2.6, "e": 3.2},
            {"w": "WE", "s": 5.0, "e": 5.4},
            {"w": "FINALLY", "s": 5.5, "e": 6.2},
            {"w": "ESCAPED", "s": 6.3, "e": 7.1},
        ]
        candidate = {
            "n": 1,
            "start": 0.0,
            "end": 11.5,
            "duration": 11.5,
            "score": 5.0,
            "quality_score": 10.0,
            "why": ["synthetic motion", "complete payoff"],
            "text": "WAIT LOOK AT THIS CHASE WE FINALLY ESCAPED",
        }
        _write_json(job / "info.json", info)
        _write_json(job / "transcript.json", words)
        _write_json(job / "analysis.json", {"job_id": job_id, "info": info, "strategy": "gaming", "candidates": [candidate]})
        result = render_candidate_clip(root, job_id, 1, topic="gta6", output_date="2026-11-21", hook="WAIT FOR THE ESCAPE")
        return {
            "valid": result["validation"]["valid"],
            "checks": result["validation"]["checks"],
            "content_quality": result["validation"]["content_quality"],
            "package_files": sorted(result["manifest"]["files"]),
            "duration_seconds": result["validation"]["observed"]["duration_seconds"],
        }


if __name__ == "__main__":
    report = run()
    print(json.dumps(report, indent=2))
    raise SystemExit(0 if report["valid"] else 1)
