"""Human-review benchmark scoring for TrendClip release decisions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class BenchmarkError(ValueError):
    """The benchmark evidence is incomplete or malformed."""


DIMENSIONS = {
    "top_three_useful": {"weight": 0.25, "target": 0.90},
    "narrative_complete": {"weight": 0.20, "target": 0.85},
    "boundary_caption_accurate": {"weight": 0.15, "target": 0.95},
    "visual_framing_good": {"weight": 0.10, "target": 0.95},
    "technical_reliable": {"weight": 0.10, "target": 1.00},
    "first_time_usable": {"weight": 0.10, "target": 0.90},
    "explainability_good": {"weight": 0.05, "target": 1.00},
}
PLATFORMS = ("windows", "macos", "linux")
CROSS_PLATFORM_WEIGHT = 0.05


def _load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BenchmarkError(f"could not read benchmark manifest: {exc}") from exc
    if not isinstance(value, dict):
        raise BenchmarkError("benchmark manifest must be a JSON object")
    return value


def score_manifest(path: Path) -> dict[str, Any]:
    """Calculate a transparent weighted score from adjudicated human evidence."""
    manifest = _load(path)
    if manifest.get("schema_version") != 1:
        raise BenchmarkError("benchmark schema_version must be 1")
    samples = manifest.get("samples")
    if not isinstance(samples, list) or not samples:
        raise BenchmarkError("benchmark needs at least one reviewed sample")
    identifiers: set[str] = set()
    for index, sample in enumerate(samples, 1):
        if not isinstance(sample, dict):
            raise BenchmarkError(f"sample {index} must be an object")
        identifier = str(sample.get("id", "")).strip()
        if not identifier or identifier in identifiers:
            raise BenchmarkError("each benchmark sample needs a unique id")
        identifiers.add(identifier)
        if int(sample.get("reviewer_count", 0)) < 2:
            raise BenchmarkError(f"sample {identifier} needs at least two reviewers")
        metrics = sample.get("metrics")
        if not isinstance(metrics, dict):
            raise BenchmarkError(f"sample {identifier} needs adjudicated metrics")
        for name in DIMENSIONS:
            if not isinstance(metrics.get(name), bool):
                raise BenchmarkError(f"sample {identifier} metric {name} must be true or false")
        failures = sample.get("critical_failures", [])
        if not isinstance(failures, list) or not all(isinstance(item, str) for item in failures):
            raise BenchmarkError(f"sample {identifier} critical_failures must be a string list")

    platform_evidence = manifest.get("platforms")
    if not isinstance(platform_evidence, dict):
        raise BenchmarkError("platforms evidence is required")
    for platform_name in PLATFORMS:
        if not isinstance(platform_evidence.get(platform_name), bool):
            raise BenchmarkError(f"platforms.{platform_name} must be true or false")

    dimensions: dict[str, Any] = {}
    total = 0.0
    missed_targets = []
    for name, config in DIMENSIONS.items():
        passed = sum(1 for sample in samples if sample["metrics"][name])
        rate = passed / len(samples)
        contribution = rate * 10 * float(config["weight"])
        total += contribution
        dimensions[name] = {
            "passed": passed,
            "total": len(samples),
            "rate": round(rate, 4),
            "target": config["target"],
            "weight": config["weight"],
            "contribution": round(contribution, 4),
        }
        if rate < float(config["target"]):
            missed_targets.append(name)

    platform_passed = sum(1 for name in PLATFORMS if platform_evidence[name])
    platform_rate = platform_passed / len(PLATFORMS)
    total += platform_rate * 10 * CROSS_PLATFORM_WEIGHT
    dimensions["cross_platform"] = {
        "passed": platform_passed,
        "total": len(PLATFORMS),
        "rate": round(platform_rate, 4),
        "target": 1.0,
        "weight": CROSS_PLATFORM_WEIGHT,
        "contribution": round(platform_rate * 10 * CROSS_PLATFORM_WEIGHT, 4),
    }
    if platform_rate < 1.0:
        missed_targets.append("cross_platform")

    critical_failures = [
        {"sample": sample["id"], "failure": failure}
        for sample in samples
        for failure in sample.get("critical_failures", [])
    ]
    score = round(total, 2)
    return {
        "schema_version": 1,
        "sample_count": len(samples),
        "score_out_of_10": score,
        "dimensions": dimensions,
        "missed_targets": missed_targets,
        "critical_failures": critical_failures,
        "release_ready": score >= 9.0 and not missed_targets and not critical_failures,
        "perfect_evidence": score == 10.0 and not missed_targets and not critical_failures,
    }

