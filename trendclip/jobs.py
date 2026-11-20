"""Atomic, durable media job state with explicit processing stages."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


STAGES = ("queued", "ingesting", "transcribing", "analyzing", "ready", "rendering", "validating", "complete")
TERMINAL = {"complete", "failed", "cancelled"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def job_path(root: Path, job_id: str) -> Path:
    return root / "state" / "jobs" / job_id / "job.json"


def read_job(root: Path, job_id: str) -> dict[str, Any] | None:
    try:
        value = json.loads(job_path(root, job_id).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def update_job(root: Path, job_id: str, *, stage: str, message: str = "", **fields: Any) -> dict[str, Any]:
    if stage not in set(STAGES) | TERMINAL:
        raise ValueError(f"invalid job stage: {stage}")
    value = read_job(root, job_id) or {"job_id": job_id, "created_at": _now(), "history": []}
    value.update(fields)
    value["stage"] = stage
    value["status"] = "failed" if stage == "failed" else ("complete" if stage == "complete" else ("cancelled" if stage == "cancelled" else "active"))
    value["message"] = str(message)[:1000]
    value["updated_at"] = _now()
    history = value.setdefault("history", [])
    history.append({"stage": stage, "message": str(message)[:1000], "at": value["updated_at"]})
    value["history"] = history[-100:]
    _atomic(job_path(root, job_id), value)
    return value


def list_jobs(root: Path, *, limit: int = 50) -> list[dict[str, Any]]:
    jobs = []
    for path in (root / "state" / "jobs").glob("*/job.json"):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            jobs.append(value)
    return sorted(jobs, key=lambda item: str(item.get("updated_at", "")), reverse=True)[:limit]
