"""Turn ranked moment evidence into a small, understandable draft set."""

from __future__ import annotations

from typing import Any, Iterable


def _component(candidate: dict[str, Any], name: str) -> float:
    return float(candidate.get("score_components", {}).get(name, 0) or 0)


def _quality(candidate: dict[str, Any]) -> float:
    return float(candidate.get("quality_score", 0) or 0)


def _energy(candidate: dict[str, Any]) -> float:
    return (
        _component(candidate, "loudness")
        + _component(candidate, "heat")
        + _component(candidate, "motion")
        + _component(candidate, "emphasis")
    )


def assemble_drafts(candidates: Iterable[dict[str, Any]], *, preferred_n: int | None = None) -> list[dict[str, Any]]:
    """Return up to three unique single-range editorial drafts.

    These are the first automatic draft recipes. Later montage assembly may join
    compatible beats, but it must use the same clear labels and uniqueness rules.
    """
    values = list(candidates)
    if not values:
        return []
    by_n = {int(item["n"]): item for item in values}
    used: set[int] = set()
    drafts: list[dict[str, Any]] = []

    def add(kind: str, label: str, layout: str, candidate: dict[str, Any] | None, reason: str) -> None:
        if candidate is None:
            return
        number = int(candidate["n"])
        if number in used:
            return
        used.add(number)
        drafts.append({
            "kind": kind,
            "label": label,
            "layout": layout,
            "candidate_n": number,
            "recommended": not drafts,
            "reason": reason,
        })

    preferred = by_n.get(int(preferred_n)) if preferred_n is not None else None
    best_story = preferred or max(values, key=lambda item: (_quality(item), float(item.get("score", 0))))
    add("best-story", "Best story", "balanced", best_story, "Strongest complete hook-to-payoff candidate")

    energy_pool = [item for item in values if int(item["n"]) not in used]
    high_energy = max(energy_pool, key=lambda item: (_energy(item), _quality(item)), default=None)
    add("high-energy", "High energy", "punch", high_energy, "Strongest combined audio, replay, motion, and emphasis evidence")

    quick_pool = [item for item in values if int(item["n"]) not in used]
    quick_hit = max(
        quick_pool,
        key=lambda item: (_quality(item) / max(float(item.get("duration", 1)), 1), _quality(item)),
        default=None,
    )
    add("quick-hit", "Quick hit", "clean", quick_hit, "Most editorial quality per second among the remaining moments")

    for item in values:
        if len(drafts) >= 3:
            break
        add("alternative", "Alternative", "balanced", item, "Next distinct ranked moment")
    return drafts
