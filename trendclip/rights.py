"""Source-rights records and hard reuse enforcement."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


ALLOWED_CATEGORIES = {"third-party-review-draft", "user-authorized", "creator-owned", "licensed", "authorized-campaign"}
BLOCKED_CATEGORIES = {"unknown", "research-only"}
PLATFORMS = {"youtube", "facebook", "tiktok"}
SCOPES = {"unknown", "noncommercial", "commercial"}


class RightsError(ValueError):
    pass


def validate_rights(value: object, *, require_reuse: bool = True) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise RightsError("choose and document the source rights before analysis")
    category = value.get("category", "unknown")
    if category not in ALLOWED_CATEGORIES | BLOCKED_CATEGORIES:
        raise RightsError("unsupported rights category")
    if require_reuse and category in BLOCKED_CATEGORIES:
        raise RightsError("unknown and research-only sources cannot be downloaded or remixed")
    reference = value.get("permission_reference", "")
    if not isinstance(reference, str) or len(reference) > 1000:
        raise RightsError("permission reference is invalid")
    if category in {"licensed", "authorized-campaign"} and not reference.strip():
        raise RightsError("licensed and campaign sources need a permission or license reference")
    platforms = value.get("allowed_platforms", [])
    if not isinstance(platforms, list) or not platforms or not set(platforms) <= PLATFORMS:
        raise RightsError("select at least one supported destination platform")
    scope = value.get("commercial_use_scope", "unknown")
    if scope not in SCOPES:
        raise RightsError("commercial-use scope is invalid")
    attribution = value.get("attribution_required", False)
    if not isinstance(attribution, bool):
        raise RightsError("attribution_required must be true or false")
    note = value.get("attribution_note", "")
    if not isinstance(note, str) or len(note) > 1000:
        raise RightsError("attribution note is invalid")
    return {
        "category": category,
        "permission_reference": reference.strip(),
        "allowed_platforms": sorted(set(platforms)),
        "commercial_use_scope": scope,
        "attribution_required": attribution,
        "attribution_note": note.strip(),
        "confirmed_at": datetime.now(timezone.utc).isoformat(),
    }
