"""Explainable highlight selection strategies for different content formats."""

from __future__ import annotations

import math
import re


ENERGY_WORDS = re.compile(r"\b(no way|wow|wait|look|incredible|important|why|how|secret|mistake|finally)\b", re.I)
PUNCH_WORDS = re.compile(r"\b(but|until|except|turns out|plot twist|actually)\b", re.I)
HOOK_WORDS = re.compile(r"\b(no way|wait|look|watch|what if|did you|how|why|secret|imagine|this is)\b", re.I)
PAYOFF_WORDS = re.compile(r"\b(finally|there it is|got it|made it|won|lost|died|failed|escaped|revealed|turns out|that's why|that is why)\b", re.I)
GAMING_EVENTS = re.compile(r"\b(win|won|fail|failed|died|kill|boss|mission|chase|escape|police|wanted|car|crash|glitch|secret|reveal|weapon|explosion|npc)\w*\b", re.I)
CONTEXT_OPENERS = re.compile(r"^(and|but|so|then|because|also|he|she|they|it|that|this|these|those|which|who)\b", re.I)


def _normalized(values):
    import numpy as np
    values = np.asarray(values, dtype=float)
    if not len(values) or values.std() < 1e-9:
        return np.zeros_like(values)
    return np.clip((values - values.mean()) / (values.std() + 1e-9), 0, None)


def _series(words, db, duration: float, heatmap, visual_signals):
    import numpy as np
    count = max(1, min(len(db), int(math.ceil(duration))))
    speech = np.zeros(count)
    emphasis = np.zeros(count)
    punch = np.zeros(count)
    for word in words:
        second = int(float(word.get("s", 0)))
        if 0 <= second < count:
            token = str(word.get("w", ""))
            speech[second] += 1
            emphasis[second] += bool(ENERGY_WORDS.search(token))
            punch[second] += bool(PUNCH_WORDS.search(token))
    heat = np.zeros(count)
    for entry in heatmap or []:
        start = max(0, int(entry.get("start_time", 0)))
        end = min(count, max(start + 1, int(math.ceil(entry.get("end_time", start + 1)))))
        heat[start:end] = float(entry.get("value", 0))
    motion = np.zeros(count)
    for entry in visual_signals or []:
        second = int(entry.get("second", -1))
        if 0 <= second < count:
            motion[second] = float(entry.get("motion", 0))
    loud = _normalized(list(db)[:count])
    return {"speech": _normalized(speech), "emphasis": _normalized(emphasis), "punch": _normalized(punch), "heat": _normalized(heat), "motion": _normalized(motion), "loudness": loud}


def _weights(strategy: str) -> dict[str, float]:
    return {
        "gaming": {"loudness": .34, "emphasis": .22, "heat": .30, "speech": .06, "motion": .08},
        "conversation": {"speech": .34, "emphasis": .22, "punch": .16, "loudness": .14, "heat": .14},
        "educational": {"speech": .35, "emphasis": .30, "loudness": .10, "heat": .15, "motion": .10},
        "comedy": {"punch": .34, "speech": .20, "loudness": .20, "heat": .20, "emphasis": .06},
        "craft": {"motion": .40, "speech": .24, "emphasis": .16, "heat": .10, "loudness": .10},
    }.get(strategy, {})


def _word_start(word) -> float:
    return float(word.get("s", 0))


def _word_end(word) -> float:
    return float(word.get("e", word.get("s", 0)))


def _text(words) -> str:
    return " ".join(str(word.get("w", "")).strip() for word in words).strip()


def _boundary_after(word, next_word=None) -> bool:
    token = str(word.get("w", "")).rstrip()
    if token.endswith((".", "?", "!")):
        return True
    return next_word is not None and _word_start(next_word) - _word_end(word) >= .65


def _snap_window(words, peak: float, duration: float, minimum: float, maximum: float):
    """Choose speech-aware boundaries around a signal peak.

    The peak proposes an event; transcript punctuation and real pauses decide where
    the candidate starts and ends. This avoids presenting a loud second as a clip
    that begins or finishes halfway through a thought.
    """
    if not words:
        start = max(0.0, peak - maximum * .42)
        return start, min(duration, start + maximum), []
    ordered = sorted(words, key=_word_start)
    floor = max(0.0, peak - maximum * .60)
    eligible = [index for index, word in enumerate(ordered) if floor <= _word_start(word) <= peak]
    start_index = eligible[0] if eligible else min(range(len(ordered)), key=lambda index: abs(_word_start(ordered[index]) - floor))
    for index in reversed(eligible):
        if index == 0 or _boundary_after(ordered[index - 1], ordered[index]):
            start_index = index
            break
    start = max(0.0, _word_start(ordered[start_index]) - .12)
    min_end = min(duration, start + minimum)
    max_end = min(duration, start + maximum)
    end_index = None
    for index in range(start_index, len(ordered)):
        end = _word_end(ordered[index])
        if end > max_end:
            break
        following = ordered[index + 1] if index + 1 < len(ordered) else None
        if end >= min_end and _boundary_after(ordered[index], following):
            end_index = index
            break
    if end_index is None:
        within = [index for index in range(start_index, len(ordered)) if _word_end(ordered[index]) <= max_end]
        end_index = within[-1] if within else start_index
    end = min(duration, max(min_end, _word_end(ordered[end_index]) + .18), max_end)
    selected = [word for word in ordered if start <= _word_start(word) < end]
    return start, end, selected


def _quality_components(segment_words, start: float, end: float, duration: float) -> dict[str, float]:
    text = _text(segment_words)
    first = str(segment_words[0].get("w", "")).strip() if segment_words else ""
    last = str(segment_words[-1].get("w", "")).strip() if segment_words else ""
    starts_cleanly = bool(segment_words) and (start <= .2 or not CONTEXT_OPENERS.search(first))
    ends_cleanly = bool(segment_words) and (end >= duration - .2 or last.endswith((".", "?", "!")) or bool(PAYOFF_WORDS.search(text)))
    return {
        "clean_start": 1.0 if starts_cleanly else 0.0,
        "clean_end": 1.0 if ends_cleanly else 0.0,
        "hook": 1.0 if HOOK_WORDS.search(text[:180]) else 0.0,
        "payoff": 1.0 if PAYOFF_WORDS.search(text) else 0.0,
        "gaming_event": 1.0 if GAMING_EVENTS.search(text) else 0.0,
    }


def select_moments(strategy: str, words, db, heatmap, duration: float, *, visual_signals=None, top: int = 8, minimum: float = 15, maximum: float = 30):
    """Return non-overlapping, explainable windows using format-specific signals."""
    import numpy as np
    weights = _weights(strategy)
    if not weights:
        raise ValueError(f"unsupported highlight strategy: {strategy}")
    signals = _series(words, db, duration, heatmap, visual_signals)
    score = np.zeros(len(signals["speech"]))
    for name, weight in weights.items():
        score += signals[name] * weight
    used = np.zeros(len(score), dtype=bool)
    picks = []
    for peak in np.argsort(-score):
        if len(picks) >= top or float(score[peak]) <= 0:
            break
        start, end, segment_words = _snap_window(words, float(peak), duration, minimum, maximum)
        if end - start < minimum or used[int(start):max(int(start) + 1, int(end))].any():
            continue
        components = {name: round(float(signals[name][peak] * weight), 3) for name, weight in weights.items()}
        quality = _quality_components(segment_words, start, end, duration)
        quality_score = (
            quality["clean_start"] * 2.2
            + quality["clean_end"] * 2.2
            + quality["hook"] * 1.8
            + quality["payoff"] * 2.4
            + quality["gaming_event"] * 1.4
        )
        # Signal strength proposes the event; completeness decides whether it is
        # usable. Keep the raw evidence so the ranking remains explainable.
        ranking_score = float(score[peak]) + quality_score * .18
        used[int(start):max(int(start) + 1, int(end))] = True
        why = [name.replace("heat", "viewer replay").replace("motion", "visual change") for name, value in sorted(components.items(), key=lambda item: item[1], reverse=True) if value > 0][:3]
        if quality["payoff"]:
            why.append("clear payoff language")
        if quality["gaming_event"]:
            why.append("gaming event language")
        warnings = []
        if not quality["clean_start"]:
            warnings.append("may depend on earlier context")
        if not quality["clean_end"]:
            warnings.append("payoff or sentence ending is uncertain")
        picks.append({"n": len(picks) + 1, "start": round(start, 2), "end": round(end, 2), "duration": round(end-start, 2), "score": round(ranking_score, 3), "quality_score": round(quality_score, 1), "strategy": strategy, "score_components": components, "quality_components": quality, "why": why[:5] or ["speech continuity"], "warnings": warnings, "text": _text(segment_words)[:500]})
    return sorted(picks, key=lambda item: item["score"], reverse=True)
