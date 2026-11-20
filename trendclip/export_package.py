"""Create a complete, locally reviewable manual-publishing package."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .codex_adapter import CodexAdapterError, invoke


DESTINATIONS = {"youtube", "facebook", "tiktok"}


def _atomic(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _srt_time(value: float) -> str:
    milliseconds = max(0, round(value * 1000))
    hours, remainder = divmod(milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{milliseconds:03d}"


def _write_srt(path: Path, words, start: float, end: float) -> None:
    selected = [word for word in words if start <= float(word["s"]) < end]
    cues = []
    for index in range(0, len(selected), 6):
        group = selected[index:index + 6]
        if not group:
            continue
        cues.append(f"{len(cues)+1}\n{_srt_time(float(group[0]['s'])-start)} --> {_srt_time(min(end, float(group[-1]['e'])+.35)-start)}\n{' '.join(str(item['w']).strip() for item in group)}\n")
    path.write_text("\n".join(cues), encoding="utf-8")


def _thumbnail(video: Path, destination: Path) -> None:
    import cv2
    capture = cv2.VideoCapture(str(video))
    capture.set(cv2.CAP_PROP_POS_MSEC, 1000)
    ok, frame = capture.read()
    capture.release()
    if not ok or not cv2.imwrite(str(destination), frame):
        raise RuntimeError("could not create the export thumbnail")


def _platform_metadata(title: str, attribution: str, topic: str, destinations: set[str]) -> dict[str, Any]:
    topic_tags = ["#GTA6", "#Gaming"] if topic == "gta6" else []
    values = {
        "youtube": {
            "title": title[:100],
            "description": f"{title}\n\nA locally edited short-form draft. {attribution}".strip(),
            "hashtags": [*topic_tags, "#Shorts"],
            "tags": [tag.removeprefix("#") for tag in topic_tags] + ["short video"],
        },
        "facebook": {
            "title": title[:255],
            "description": f"{title}\n\nCreated as a local review draft. {attribution}".strip(),
            "hashtags": topic_tags,
        },
        "tiktok": {
            "caption": f"{title} {' '.join(topic_tags)} {attribution}".strip()[:2200],
            "hashtags": topic_tags,
        },
    }
    return {name: values[name] for name in ("youtube", "facebook", "tiktok") if name in destinations}


def build_export_package(root: Path, destination: Path, *, video: Path, metadata: dict[str, Any], words, candidate: dict[str, Any], rights: dict[str, Any], destinations: set[str] | None = None) -> dict[str, Any]:
    """Add captions, thumbnail, provenance, platform drafts and a checksummed manifest."""
    captions = destination / "captions.srt"
    thumbnail = destination / "thumbnail.png"
    _write_srt(captions, words, float(candidate["start"]), float(candidate["end"]))
    _thumbnail(video, thumbnail)
    title = str(metadata.get("suggested_title") or "Short video")[:100]
    attribution = str(rights.get("attribution_note") or "").strip()
    selected = set(destinations or DESTINATIONS)
    if not selected or not selected <= DESTINATIONS:
        raise ValueError("destinations must include YouTube, Facebook, or TikTok")
    platforms = _platform_metadata(title, attribution, str(metadata.get("topic_slug", "")), selected)
    codex_status = {"used": False, "reason": "disabled"}
    try:
        settings = json.loads((root / "config" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        settings = {"codex": {"enabled": False}}
    config = settings.get("codex", {})
    if config.get("enabled", False):
        try:
            generated = invoke(root, "publishing-metadata-draft", {"title": title, "destinations": sorted(selected), "source": metadata.get("source_references", []), "transcript_excerpt": candidate.get("text", ""), "rights": rights, "rules": "Natural copy, no misleading clickbait, no hashtag stuffing."}, enabled=True, timeout=int(config.get("timeout_seconds", 120)), max_output_bytes=int(config.get("max_output_bytes", 262144)))
            platforms = {name: generated[name] for name in selected if name in generated}
            if set(platforms) != selected:
                raise CodexAdapterError("Codex metadata omitted a selected destination")
            codex_status = {"used": True, "task": "publishing-metadata-draft"}
        except CodexAdapterError as exc:
            codex_status = {"used": False, "reason": str(exc), "fallback": "deterministic-metadata"}
    provenance = {"generated_at": datetime.now(timezone.utc).isoformat(), "source_references": metadata.get("source_references", []), "transformation": metadata.get("content_type"), "destinations": sorted(selected), "rights": rights, "automation": {"publishing": "manual-only", "codex": codex_status}}
    _atomic(destination / "platform-metadata.json", platforms)
    _atomic(destination / "provenance.json", provenance)
    files = {}
    for path in sorted(destination.iterdir()):
        if path.is_file() and path.name != "export-manifest.json":
            files[path.name] = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "files": files}
    _atomic(destination / "export-manifest.json", manifest)
    return manifest
