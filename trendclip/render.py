"""Reusable FFmpeg renderer for original graphical vertical videos."""

from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, List

from .config import TopicConfig
from .raster import render_scene


class RenderError(RuntimeError):
    pass


Runner = Callable[..., subprocess.CompletedProcess]


def write_scene_image(config: TopicConfig, index: int, destination: Path) -> None:
    """Create a self-contained original raster scene using configuration data."""
    scene = config.scenes[index]
    render_scene(
        destination,
        width=config.width,
        height=config.height,
        background=scene.background,
        accent=scene.accent,
        eyebrow=scene.eyebrow,
        headline=scene.headline,
        body=scene.body,
        index=index,
        count=len(config.scenes),
    )


def build_filter_graph(config: TopicConfig) -> tuple[str, float]:
    # Each numbered input is an original scene rasterized by this package.
    parts: List[str] = [
        f"[{i}:v]scale={config.width}:{config.height},format=yuv420p,setpts=PTS-STARTPTS[v{i}]"
        for i in range(len(config.scenes))
    ]
    elapsed = config.scenes[0].duration
    previous = "v0"
    for index in range(1, len(config.scenes)):
        offset = elapsed - config.transition
        output = f"x{index}"
        parts.append(
            f"[{previous}][v{index}]xfade=transition=fade:duration={config.transition}:"
            f"offset={offset:.3f}[{output}]"
        )
        previous = output
        elapsed += config.scenes[index].duration - config.transition
    # An original, quiet two-tone synthetic bed; no downloaded or third-party audio.
    parts.extend(
        [
            f"sine=f=110:r=48000:d={elapsed:.3f},volume=0.028[a0]",
            f"sine=f=220:r=48000:d={elapsed:.3f},volume=0.012[a1]",
            f"[a0][a1]amix=inputs=2:duration=longest,afade=t=in:st=0:d=1.2,"
            f"afade=t=out:st={max(0.0, elapsed - 1.2):.3f}:d=1.2[aout]",
        ]
    )
    return ";".join(parts), elapsed


def render_clip(
    config: TopicConfig,
    output_file: Path,
    *,
    ffmpeg: str = "ffmpeg",
    runner: Runner = subprocess.run,
) -> Dict[str, object]:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temporary_output = output_file.with_suffix(".partial.mp4")
    with tempfile.TemporaryDirectory(prefix="trendclip-") as temporary:
        temporary_dir = Path(temporary)
        image_paths = []
        for index in range(len(config.scenes)):
            image_path = temporary_dir / f"scene-{index}.ppm"
            write_scene_image(config, index, image_path)
            image_paths.append(image_path)
        graph, expected_duration = build_filter_graph(config)
        final_video = f"x{len(config.scenes) - 1}"
        command: List[str] = [ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
        ]
        for image_path, scene in zip(image_paths, config.scenes):
            command.extend(
                ["-loop", "1", "-framerate", str(config.fps), "-t", str(scene.duration), "-i", str(image_path)]
            )
        command.extend([
            "-filter_complex",
            graph,
            "-map",
            f"[{final_video}]",
            "-map",
            "[aout]",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-r",
            str(config.fps),
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(temporary_output),
        ])
        try:
            runner(command, check=True, capture_output=True, text=True)
        except (OSError, subprocess.CalledProcessError) as exc:
            temporary_output.unlink(missing_ok=True)
            details = getattr(exc, "stderr", None) or str(exc)
            raise RenderError(f"FFmpeg render failed: {details.strip()}") from exc
    temporary_output.replace(output_file)
    digest = hashlib.sha256(output_file.read_bytes()).hexdigest()
    return {
        "renderer": "trendclip-studio-python-raster-ffmpeg",
        "expected_duration_seconds": round(expected_duration, 3),
        "sha256": digest,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def write_metadata(
    config: TopicConfig,
    destination: Path,
    video_file: Path,
    render_details: Dict[str, object],
    validation: Dict[str, object],
) -> None:
    metadata = dict(config.metadata)
    metadata.update(
        {
            "project_name": "TrendClip Studio",
            "topic": config.topic_name,
            "topic_slug": config.slug,
            "mode": config.mode,
            "video_file": video_file.name,
            "generated_timestamp": render_details["generated_at"],
            "render": render_details,
            "validation_status": "passed" if validation.get("valid") else "failed",
            "content_disclosure": config.metadata["content_disclosure"],
            "validated_sha256": validation.get("sha256"),
        }
    )
    destination.write_text(json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

