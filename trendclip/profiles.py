"""Strict, configuration-driven content niche profiles."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
STRATEGIES = {"educational", "conversation", "gaming", "comedy", "craft"}


class ProfileError(ValueError):
    pass


@dataclass(frozen=True)
class DiscoveryFilters:
    hours: int
    min_duration: int
    max_duration: int
    channels: tuple[str, ...]
    limit: int


@dataclass(frozen=True)
class NicheProfile:
    slug: str
    name: str
    query: str
    keywords: tuple[str, ...]
    exclusions: tuple[str, ...]
    strategy: str
    language: str
    discovery: DiscoveryFilters

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _strings(value: object, field: str, *, allow_empty: bool = False) -> tuple[str, ...]:
    if not isinstance(value, list) or (not value and not allow_empty):
        raise ProfileError(f"{field} must be {'a' if not allow_empty else 'an'} string list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ProfileError(f"{field} contains an invalid value")
    return tuple(dict.fromkeys(item.strip() for item in value))


def _profile(value: object, index: int) -> NicheProfile:
    if not isinstance(value, dict):
        raise ProfileError(f"profile {index} must be an object")
    slug, name, query = value.get("slug"), value.get("name"), value.get("query")
    if not isinstance(slug, str) or not SLUG.fullmatch(slug):
        raise ProfileError(f"profile {index} has an invalid slug")
    if not isinstance(name, str) or not name.strip() or len(name) > 80:
        raise ProfileError(f"profile {slug} has an invalid name")
    if not isinstance(query, str) or not query.strip() or len(query) > 160:
        raise ProfileError(f"profile {slug} has an invalid query")
    strategy = value.get("strategy")
    if strategy not in STRATEGIES:
        raise ProfileError(f"profile {slug} has an unsupported strategy")
    language = value.get("language")
    if not isinstance(language, str) or not re.fullmatch(r"[a-z]{2}(?:-[A-Z]{2})?", language):
        raise ProfileError(f"profile {slug} has an invalid language")
    raw_filters = value.get("discovery")
    if not isinstance(raw_filters, dict):
        raise ProfileError(f"profile {slug} needs discovery filters")
    hours = raw_filters.get("hours")
    minimum = raw_filters.get("min_duration")
    maximum = raw_filters.get("max_duration")
    limit = raw_filters.get("limit")
    if not isinstance(hours, int) or not 1 <= hours <= 720:
        raise ProfileError(f"profile {slug} discovery hours must be 1..720")
    if not isinstance(minimum, int) or not isinstance(maximum, int) or not 0 <= minimum < maximum <= 14_400:
        raise ProfileError(f"profile {slug} has invalid duration filters")
    if not isinstance(limit, int) or not 1 <= limit <= 50:
        raise ProfileError(f"profile {slug} result limit must be 1..50")
    return NicheProfile(
        slug=slug,
        name=name.strip(),
        query=query.strip(),
        keywords=_strings(value.get("keywords"), f"profile {slug} keywords"),
        exclusions=_strings(value.get("exclusions"), f"profile {slug} exclusions", allow_empty=True),
        strategy=strategy,
        language=language,
        discovery=DiscoveryFilters(hours, minimum, maximum, _strings(raw_filters.get("channels"), f"profile {slug} channels", allow_empty=True), limit),
    )


def load_profiles(path: Path) -> list[NicheProfile]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ProfileError(f"cannot load profiles: {exc}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1 or not isinstance(raw.get("profiles"), list):
        raise ProfileError("profiles configuration must use schema version 1")
    profiles = [_profile(value, index) for index, value in enumerate(raw["profiles"])]
    if not profiles:
        raise ProfileError("at least one profile is required")
    slugs = [profile.slug for profile in profiles]
    if len(slugs) != len(set(slugs)):
        raise ProfileError("profile slugs must be unique")
    return profiles


def load_profile(path: Path, slug: str) -> NicheProfile:
    for profile in load_profiles(path):
        if profile.slug == slug:
            return profile
    raise ProfileError(f"unknown profile: {slug}")
