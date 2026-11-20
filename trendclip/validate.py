"""Technical validation for rendered exports."""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
from datetime import datetime, timezone
from fractions import Fraction
from pathlib import Path
from typing import Callable, Dict


Runner = Callable[..., subprocess.CompletedProcess]


def inspect_media_quality(
    path: Path,
    *,
    allow_static: bool = False,
    allow_silence: bool = False,
    ffmpeg: str = "ffmpeg",
    runner: Runner = subprocess.run,
) -> Dict[str, object]:
    """Detect material black, frozen, or silent spans in the rendered artifact."""
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostats",
        "-i",
        str(path),
        "-vf",
        "blackdetect=d=0.75:pic_th=0.98,freezedetect=n=-50dB:d=2.0",
        "-af",
        "silencedetect=n=-50dB:d=3.0",
        "-f",
        "null",
        "-",
    ]
    try:
        completed = runner(command, capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"valid": False, "checks": {}, "errors": [f"content inspection failed: {exc}"]}
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "ffmpeg content inspection failed")[-1000:].strip()
        return {"valid": False, "checks": {}, "errors": [message]}
    log = completed.stderr or ""
    black = [float(value) for value in re.findall(r"black_duration:([0-9.]+)", log)]
    frozen = [float(value) for value in re.findall(r"freeze_duration:\s*([0-9.]+)", log)]
    silent = [float(value) for value in re.findall(r"silence_duration:\s*([0-9.]+)", log)]
    checks = {
        "no_black_span_over_0_75_seconds": not black,
        "no_frozen_span_over_2_seconds": allow_static or not frozen,
        "no_silent_span_over_3_seconds": allow_silence or not silent,
    }
    errors = [name for name, passed in checks.items() if not passed]
    return {
        "valid": not errors,
        "checks": checks,
        "errors": errors,
        "observed": {
            "black_spans_seconds": black,
            "frozen_spans_seconds": frozen,
            "silent_spans_seconds": silent,
        },
        "policy": {"allow_static": allow_static, "allow_silence": allow_silence},
    }


def add_content_quality(validation: Dict[str, object], quality: Dict[str, object]) -> Dict[str, object]:
    """Combine structural ffprobe checks with rendered-content checks."""
    combined = dict(validation)
    combined["content_quality"] = quality
    combined["errors"] = list(validation.get("errors", [])) + list(quality.get("errors", []))
    combined["valid"] = bool(validation.get("valid")) and bool(quality.get("valid"))
    return combined


def probe_video(
    path: Path,
    *,
    expected_fps: int = 30,
    minimum_duration: float = 15.0,
    maximum_duration: float = 30.0,
    ffprobe: str = "ffprobe",
    runner: Runner = subprocess.run,
) -> Dict[str, object]:
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_streams",
        "-show_format",
        "-of",
        "json",
        str(path),
    ]
    try:
        completed = runner(command, check=True, capture_output=True, text=True)
        payload = json.loads(completed.stdout)
    except (OSError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"ffprobe failed: {exc}"]}
    streams = payload.get("streams", [])
    video = next((stream for stream in streams if stream.get("codec_type") == "video"), {})
    audio = next((stream for stream in streams if stream.get("codec_type") == "audio"), {})
    duration = float(payload.get("format", {}).get("duration", 0.0))
    try:
        frame_rate = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        frame_rate = 0.0
    errors = []
    checks = {
        "width_1080": video.get("width") == 1080,
        "height_1920": video.get("height") == 1920,
        "video_h264": video.get("codec_name") == "h264",
        "pixel_format_yuv420p": video.get("pix_fmt") == "yuv420p",
        "audio_aac": audio.get("codec_name") == "aac",
        "frame_rate_matches_config": abs(frame_rate - expected_fps) < 0.01,
        f"duration_{minimum_duration:g}_to_{maximum_duration:g}_seconds": minimum_duration <= duration <= maximum_duration,
        "mp4_container": "mp4" in payload.get("format", {}).get("format_name", ""),
    }
    for name, passed in checks.items():
        if not passed:
            errors.append(name)
    try:
        digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        errors.append(f"cannot hash validated artifact: {exc}")
        digest = None
    return {
        "valid": not errors,
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "sha256": digest,
        "checks": checks,
        "errors": errors,
        "observed": {
            "width": video.get("width"),
            "height": video.get("height"),
            "video_codec": video.get("codec_name"),
            "pixel_format": video.get("pix_fmt"),
            "frame_rate": video.get("avg_frame_rate"),
            "frame_rate_decimal": round(frame_rate, 3),
            "audio_codec": audio.get("codec_name"),
            "duration_seconds": round(duration, 3),
            "container": payload.get("format", {}).get("format_name"),
            "size_bytes": int(payload.get("format", {}).get("size", 0)),
        },
    }


def write_validation(result: Dict[str, object], destination: Path) -> None:
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")

