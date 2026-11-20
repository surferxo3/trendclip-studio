"""Strict loading and validation for topic/video configuration."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

from .raster import FONT


SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


class ConfigError(ValueError):
    """Raised when a configuration file is unsafe or malformed."""


@dataclass(frozen=True)
class Scene:
    eyebrow: str
    headline: str
    body: str
    duration: float
    background: str
    accent: str


@dataclass(frozen=True)
class TopicConfig:
    slug: str
    topic_name: str
    language: str
    keywords: List[str]
    exclusions: List[str]
    mode: str
    width: int
    height: int
    fps: int
    transition: float
    scenes: List[Scene]
    metadata: Dict[str, Any]


def _require(mapping: Dict[str, Any], key: str, expected: type) -> Any:
    value = mapping.get(key)
    if not isinstance(value, expected):
        raise ConfigError(f"{key!r} must be {expected.__name__}")
    return value


def _clean_text(value: Any, field: str, limit: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field!r} must be a non-empty string")
    if len(value) > limit or "\x00" in value:
        raise ConfigError(f"{field!r} is too long or contains a NUL byte")
    return value.strip()


def load_topic(path: Path) -> TopicConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load configuration: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be an object")

    slug = _clean_text(raw.get("slug"), "slug", 64)
    if not SLUG_RE.fullmatch(slug):
        raise ConfigError("slug must contain only lowercase letters, digits, '_' or '-'")
    video = _require(raw, "video", dict)
    size = video.get("size")
    if size != [1080, 1920]:
        raise ConfigError("the initial renderer requires a 1080x1920 video size")
    fps = video.get("fps")
    if not isinstance(fps, int) or not 24 <= fps <= 60:
        raise ConfigError("fps must be an integer from 24 to 60")
    transition = video.get("transition_seconds")
    if not isinstance(transition, (int, float)) or not 0 <= transition <= 1:
        raise ConfigError("transition_seconds must be between 0 and 1")
    scene_data = _require(raw, "scenes", list)
    if not 2 <= len(scene_data) <= 12:
        raise ConfigError("scenes must contain between 2 and 12 entries")
    scenes = []
    for index, item in enumerate(scene_data):
        if not isinstance(item, dict):
            raise ConfigError(f"scene {index} must be an object")
        duration = item.get("duration")
        if not isinstance(duration, (int, float)) or not 1.5 <= duration <= 8:
            raise ConfigError(f"scene {index} duration must be between 1.5 and 8 seconds")
        background = item.get("background")
        accent = item.get("accent")
        if not isinstance(background, str) or not HEX_RE.fullmatch(background):
            raise ConfigError(f"scene {index} background must be a six-digit hex color")
        if not isinstance(accent, str) or not HEX_RE.fullmatch(accent):
            raise ConfigError(f"scene {index} accent must be a six-digit hex color")
        eyebrow = _clean_text(item.get("eyebrow"), f"scene {index} eyebrow", 80)
        headline = _clean_text(item.get("headline"), f"scene {index} headline", 180)
        body = _clean_text(item.get("body"), f"scene {index} body", 220)
        if len(eyebrow) > 30 or len(body) > 45:
            raise ConfigError(f"scene {index} eyebrow/body exceeds the safe layout width")
        headline_lines = headline.splitlines()
        if len(headline_lines) > 3 or any(len(line) > 18 for line in headline_lines):
            raise ConfigError(f"scene {index} headline exceeds the safe layout bounds")
        unsupported = set((eyebrow + headline + body).upper()) - set(FONT) - {"\n"}
        if unsupported:
            raise ConfigError(f"scene {index} contains unsupported glyphs: {sorted(unsupported)!r}")
        scenes.append(
            Scene(
                eyebrow=eyebrow,
                headline=headline,
                body=body,
                duration=float(duration),
                background=background,
                accent=accent,
            )
        )
    for key in ("keywords", "exclusions"):
        values = _require(raw, key, list)
        if not all(isinstance(value, str) for value in values):
            raise ConfigError(f"{key!r} entries must be strings")
    metadata = _require(raw, "metadata", dict)
    for key in (
        "suggested_title",
        "description",
        "hashtags",
        "content_type",
        "source_references",
        "asset_provenance",
        "usage_rights_review_status",
        "content_disclosure",
    ):
        if key not in metadata:
            raise ConfigError(f"metadata is missing {key!r}")
    if not isinstance(metadata["source_references"], list) or not metadata["source_references"]:
        raise ConfigError("metadata.source_references must be a non-empty list")
    for key in ("suggested_title", "description", "content_type", "usage_rights_review_status", "content_disclosure"):
        _clean_text(metadata[key], f"metadata.{key}", 1000)
    hashtags = metadata["hashtags"]
    if not isinstance(hashtags, list) or not hashtags or not all(
        isinstance(value, str) and value.startswith("#") and len(value) <= 80 for value in hashtags
    ):
        raise ConfigError("metadata.hashtags must be a non-empty list of bounded hashtags")
    provenance = metadata["asset_provenance"]
    if not isinstance(provenance, list) or not provenance or not all(
        isinstance(value, str) and 0 < len(value) <= 500 for value in provenance
    ):
        raise ConfigError("metadata.asset_provenance must be a non-empty list of bounded strings")
    for index, reference in enumerate(metadata["source_references"]):
        if not isinstance(reference, dict):
            raise ConfigError(f"source reference {index} must be an object")
        for key in ("title", "url", "publisher", "retrieved_at"):
            _clean_text(reference.get(key), f"source reference {index}.{key}", 500)
        parsed = urlparse(reference["url"])
        if parsed.scheme != "https" or not parsed.hostname:
            raise ConfigError(f"source reference {index} must use an absolute HTTPS URL")
        try:
            date.fromisoformat(reference["retrieved_at"])
        except ValueError as exc:
            raise ConfigError(f"source reference {index} has an invalid retrieval date") from exc
        supports = reference.get("supports")
        if not isinstance(supports, list) or not supports or not all(
            isinstance(value, str) and 0 < len(value) <= 300 for value in supports
        ):
            raise ConfigError(f"source reference {index}.supports must be a non-empty string list")

    return TopicConfig(
        slug=slug,
        topic_name=_clean_text(raw.get("topic_name"), "topic_name", 100),
        language=_clean_text(raw.get("language"), "language", 30),
        keywords=list(raw["keywords"]),
        exclusions=list(raw["exclusions"]),
        mode=_clean_text(raw.get("mode"), "mode", 30),
        width=1080,
        height=1920,
        fps=fps,
        transition=float(transition),
        scenes=scenes,
        metadata=dict(metadata),
    )


def validate_slug(value: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise ConfigError("invalid topic slug")
    return value


def validate_date(value: str) -> str:
    if not DATE_RE.fullmatch(value):
        raise ConfigError("date must use YYYY-MM-DD")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ConfigError("date is not a real calendar date") from exc
    return value

