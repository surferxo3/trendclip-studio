"""Turn ranked moment evidence into a small, understandable draft set."""

from __future__ import annotations

from typing import Any, Iterable


MIN_DRAFT_QUALITY = 6.0


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


def editorial_issues(candidate: dict[str, Any]) -> list[str]:
    """Explain why a candidate must not be presented as a ready draft."""
    issues: list[str] = []
    quality = _quality(candidate)
    if quality < MIN_DRAFT_QUALITY:
        issues.append(f"editorial quality {quality:.1f}/10 is below {MIN_DRAFT_QUALITY:.1f}")
    components = candidate.get("quality_components")
    if isinstance(components, dict) and components:
        if not float(components.get("clean_start", 0) or 0):
            issues.append("opening may depend on earlier context")
        if not float(components.get("clean_end", 0) or 0):
            issues.append("ending or payoff is uncertain")
        if not any(float(components.get(name, 0) or 0) for name in ("hook", "payoff", "gaming_event")):
            issues.append("no clear hook, payoff, or gaming event was detected")
    return issues


def editorial_summary(candidates: Iterable[dict[str, Any]], *, preferred_n: int | None = None) -> dict[str, Any]:
    """Return drafts plus a truthful ready/no-result status for the UI."""
    values = list(candidates)
    drafts = assemble_drafts(values, preferred_n=preferred_n)
    assessments = [
        {"candidate_n": int(item["n"]), "eligible": not editorial_issues(item), "issues": editorial_issues(item)}
        for item in values
    ]
    ready = bool(drafts)
    return {
        "drafts": drafts,
        "editorial_status": "ready" if ready else "no-suitable-moment",
        "editorial_message": (
            f"{len(drafts)} review-ready draft{'s' if len(drafts) != 1 else ''} found."
            if ready
            else "No strong complete moment was found. Try another source instead of forcing a weak clip."
        ),
        "candidate_assessments": assessments,
    }


def _story_reason(candidate: dict[str, Any]) -> str:
    components = candidate.get("quality_components")
    if not isinstance(components, dict) or not components:
        return "Highest editorial quality among the eligible moments"
    hook = bool(components.get("hook"))
    payoff = bool(components.get("payoff"))
    gaming_event = bool(components.get("gaming_event"))
    if hook and payoff:
        return "Strongest complete hook-to-payoff candidate"
    if hook and gaming_event:
        return "Strongest clean candidate with a clear hook and gaming event"
    if payoff:
        return "Strongest clean candidate with a clear payoff"
    if gaming_event:
        return "Strongest clean candidate with a detected gaming event"
    return "Highest editorial quality among the eligible moments"


def assemble_drafts(candidates: Iterable[dict[str, Any]], *, preferred_n: int | None = None) -> list[dict[str, Any]]:
    """Return up to three unique single-range editorial drafts.

    These are the first automatic draft recipes. Later montage assembly may join
    compatible beats, but it must use the same clear labels and uniqueness rules.
    """
    values = [item for item in candidates if not editorial_issues(item)]
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
    add("best-story", "Best story", "balanced", best_story, _story_reason(best_story))

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
