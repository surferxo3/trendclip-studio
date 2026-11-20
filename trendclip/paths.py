"""Filesystem boundary helpers."""

from pathlib import Path


class UnsafePathError(ValueError):
    pass


def ensure_within(path: Path, root: Path) -> Path:
    resolved_path = path.resolve()
    resolved_root = root.resolve()
    try:
        resolved_path.relative_to(resolved_root)
    except ValueError as exc:
        raise UnsafePathError(f"path escapes project boundary: {resolved_path}") from exc
    return resolved_path


def output_directory(project_root: Path, output_root: Path, topic: str, date: str) -> Path:
    safe_root = ensure_within(output_root, project_root)
    return ensure_within(safe_root / topic / date, safe_root)

