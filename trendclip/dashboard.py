"""Local-only dashboard and control API for TrendClip Studio."""

from __future__ import annotations

import json
import mimetypes
import secrets
import subprocess
import sys
import threading
import re
import os
import signal
import webbrowser
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, Optional
from urllib.parse import unquote, urlparse

from .config import ConfigError, load_topic, validate_date, validate_slug
from .candidate import render_candidate
from .discovery import DiscoveryError, discover_with_trends, discover_youtube_profile, inspect_youtube_url, save_report
from .paths import ensure_within
from .media_pipeline import MediaPipelineError, job_id_for_url
from .profiles import ProfileError, load_profile, load_profiles
from .rights import RightsError, validate_rights
from .jobs import list_jobs, read_job, update_job
from .codex_adapter import CodexAdapterError, availability as codex_availability, invoke as invoke_codex


MAX_REQUEST_BYTES = 64_000
PLATFORMS = {"youtube", "facebook", "tiktok"}
LOG_LOCK = threading.Lock()
WORKERS_LOCK = threading.Lock()
WORKER_LIMIT = threading.BoundedSemaphore(2)
ACTIVE_WORKERS: Dict[str, subprocess.Popen] = {}
ACTIVE_JOB_IDS: set[str] = set()


def _claim_job(job_id: str) -> None:
    if not job_id:
        return
    with WORKERS_LOCK:
        if job_id in ACTIVE_JOB_IDS:
            raise MediaPipelineError("This source is already processing. Wait for it to finish or cancel the active job.")
        ACTIVE_JOB_IDS.add(job_id)


def _release_job(job_id: str) -> None:
    if not job_id:
        return
    with WORKERS_LOCK:
        ACTIVE_JOB_IDS.discard(job_id)
        ACTIVE_WORKERS.pop(job_id, None)


def _worker_process_options(platform_name: str = os.name) -> Dict[str, object]:
    """Create an independently cancellable worker on every supported OS."""
    if platform_name == "nt":
        return {"creationflags": int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0))}
    return {"start_new_session": True}


def _terminate_worker(process: subprocess.Popen, platform_name: str = os.name) -> None:
    """Stop a worker and its media children without POSIX-only calls on Windows."""
    if process.poll() is not None:
        return
    if platform_name == "nt":
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                text=True,
                timeout=15,
            )
        except (OSError, subprocess.TimeoutExpired):
            completed = None
        if (completed is None or completed.returncode != 0) and process.poll() is None:
            process.terminate()
        return
    os.killpg(process.pid, signal.SIGTERM)


def _log_event(root: Path, event: str, message: str, level: str = "info") -> None:
    safe_message = str(message).replace(str(root), "<project>").replace(str(Path.home()), "<home>")
    safe_message = re.sub(r"(?i)(cookie|authorization|token|api[_-]?key)(\s*[:=]\s*)[^\s,;]+", r"\1\2<redacted>", safe_message)
    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event": event,
        "message": safe_message[:3000],
    }
    path = root / "state" / "logs" / "studio.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    with LOG_LOCK, path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _run_media_worker(root: Path, arguments, timeout: int = 3600):
    operation_id = secrets.token_hex(6)
    operation = arguments[0] if arguments else "unknown"
    job_id = ""
    if operation == "analyze" and "--url" in arguments:
        job_id = job_id_for_url(str(arguments[arguments.index("--url") + 1]))
    elif "--job-id" in arguments:
        job_id = str(arguments[arguments.index("--job-id") + 1])
    correlation = f"operation_id={operation_id} job_id={job_id or 'none'} action={operation}"
    _log_event(root, "media-worker-start", correlation)
    _claim_job(job_id)
    try:
        with WORKER_LIMIT:
            process = subprocess.Popen(
                [sys.executable, "-m", "trendclip.media_worker", "--root", str(root), *arguments],
                cwd=root,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                **_worker_process_options(),
            )
            if job_id:
                with WORKERS_LOCK:
                    ACTIVE_WORKERS[job_id] = process
            try:
                stdout, stderr = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                _terminate_worker(process)
                process.communicate()
                raise
            finally:
                _release_job(job_id)
        returncode = process.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        _release_job(job_id)
        _log_event(root, "media-worker-error", f"{correlation} {exc}", "error")
        raise MediaPipelineError(f"media worker could not complete: {exc}") from exc
    if returncode != 0:
        message = (stderr or stdout or "media worker failed")[-1800:].strip()
        try:
            structured_error = json.loads(stdout)
            message = str(structured_error.get("error") or message)
        except json.JSONDecodeError:
            pass
        _log_event(root, "media-worker-error", f"{correlation} {message}", "error")
        raise MediaPipelineError(message)
    try:
        result = json.loads(stdout)
        _log_event(root, "media-worker-complete", correlation)
        return result
    except json.JSONDecodeError as exc:
        raise MediaPipelineError("media worker returned an unreadable result") from exc


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def codex_smoke_test(root: Path) -> dict:
    """Run one bounded synthetic semantic-ranking task through the installed CLI."""
    settings = _read_json(root / "config" / "settings.json", {"codex": {"enabled": False}})
    config = settings.get("codex", {})
    payload = {
        "strategy": "gaming",
        "candidates": [
            {"id": "1", "text": "But the speaker continues without showing the result.", "start": 5, "end": 24, "warnings": ["payoff is uncertain"]},
            {"id": "2", "text": "Wait, look at this police chase. The car flips, lands, and finally we escaped!", "start": 30, "end": 52, "warnings": []},
            {"id": "3", "text": "Here is the settings menu and an ordinary option change.", "start": 60, "end": 80, "warnings": []},
        ],
    }
    return invoke_codex(
        root,
        "semantic-highlight-rerank",
        payload,
        enabled=bool(config.get("enabled", False)),
        timeout=int(config.get("timeout_seconds", 120)),
        max_output_bytes=int(config.get("max_output_bytes", 262_144)),
    )


def _save_discovery_safely(report: Dict[str, object], path: Path) -> Dict[str, object]:
    """Never replace a useful discovery cache with a transient empty refresh."""
    previous = _read_json(path, {})
    if not report.get("candidates") and previous.get("candidates"):
        previous["refresh_warning"] = "The latest refresh returned no usable metadata; the previous successful list was preserved."
        previous["source_errors"] = list(previous.get("source_errors", [])) + list(report.get("source_errors", []))
        save_report(previous, path)
        return previous
    save_report(report, path)
    return report


def project_status(root: Path) -> Dict[str, object]:
    topics = sorted(path.stem for path in (root / "config" / "topics").glob("*.json"))
    latest = None
    output_root = root / "output"
    validations = sorted(output_root.glob("*/*/validation.json"), reverse=True)
    for validation_path in validations:
        destination = validation_path.parent
        video = destination / "clip-001.mp4"
        metadata_path = destination / "clip-001.json"
        if not video.is_file() or not metadata_path.is_file():
            continue
        validation = _read_json(validation_path, {})
        metadata = _read_json(metadata_path, {})
        relative = video.relative_to(output_root).as_posix()
        variations = []
        for variation_video in sorted(destination.glob("clip-*.mp4")):
            if variation_video.name == "clip-001.mp4":
                continue
            kind = variation_video.stem.removeprefix("clip-")
            variation_metadata = _read_json(destination / f"clip-{kind}.json", {})
            variation_validation = _read_json(destination / f"validation-{kind}.json", {})
            variations.append({
                "kind": kind,
                "layout": variation_metadata.get("draft", {}).get("layout", "balanced"),
                "video_url": f"/media/{variation_video.relative_to(output_root).as_posix()}",
                "valid": bool(variation_validation.get("valid")),
            })
        latest = {
            "topic": destination.parent.name,
            "date": destination.name,
            "video_url": f"/media/{relative}",
            "video_path": str(video),
            "validation": validation,
            "metadata": metadata,
            "variations": variations,
        }
        break
    reports = {}
    for topic in topics:
        report_path = root / "state" / "discovery" / topic / "latest.json"
        report = _read_json(report_path, None)
        if report:
            reports[topic] = report
    tracking = _read_json(root / "state" / "tracking.json", {"records": []})
    profiles_path = root / "config" / "profiles.json"
    profiles = [profile.as_dict() for profile in load_profiles(profiles_path)] if profiles_path.is_file() else []
    # Version 1 presents the focused GTA 6 experience. Other profiles remain
    # available as extension examples without cluttering the default UI.
    focused_profiles = [profile for profile in profiles if profile["slug"] == "gta6"] or profiles[:1]
    profile_slugs = [profile["slug"] for profile in focused_profiles]
    settings = _read_json(root / "config" / "settings.json", {"browser_session": {"enabled": False}, "codex": {"enabled": False}, "publishing": {"mode": "manual-only"}})
    for profile in profile_slugs:
        report_path = root / "state" / "discovery" / profile / "latest.json"
        report = _read_json(report_path, None)
        if report:
            reports[profile] = report
    return {
        "project": "TrendClip Studio",
        "version": "0.5.0",
        "topics": profile_slugs or topics,
        "profiles": focused_profiles,
        "latest_export": latest,
        "discovery": reports,
        "tracking": tracking,
        "media_job": _read_json(root / "state" / "media" / "latest.json", None),
        "jobs": list_jobs(root),
        "settings": settings,
        "codex": {**codex_availability(), "enabled": bool(settings.get("codex", {}).get("enabled", False))},
        "publishing": {
            "mode": "manual-only",
            "youtube": "disabled",
            "facebook": "disabled",
            "tiktok": "disabled",
            "scheduling": "disabled",
        },
    }


def _atomic_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def make_handler(root: Path):
    dashboard_root = root / "dashboard"

    class Handler(BaseHTTPRequestHandler):
        server_version = "TrendClipDashboard/0.5.0"

        def _headers(self, status: int, content_type: str, length: Optional[int] = None, extra=None) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("X-Frame-Options", "DENY")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data: https://i.ytimg.com https://*.googleusercontent.com; media-src 'self'; connect-src 'self'; frame-ancestors 'none'",
            )
            if length is not None:
                self.send_header("Content-Length", str(length))
            for name, value in (extra or {}).items():
                self.send_header(name, value)
            self.end_headers()

        def _serve_video(self, target: Path) -> None:
            size = target.stat().st_size
            start, end, status = 0, size - 1, 200
            range_header = self.headers.get("Range", "")
            if range_header.startswith("bytes="):
                try:
                    first, last = range_header.removeprefix("bytes=").split(",", 1)[0].split("-", 1)
                    if first:
                        start = int(first)
                    if last:
                        end = int(last)
                    end = min(end, size - 1)
                    if start < 0 or start > end:
                        raise ValueError
                    status = 206
                except ValueError:
                    self._headers(416, "video/mp4", 0, {"Content-Range": f"bytes */{size}"})
                    return
            length = end - start + 1
            extra = {"Accept-Ranges": "bytes"}
            if status == 206:
                extra["Content-Range"] = f"bytes {start}-{end}/{size}"
            self._headers(status, "video/mp4", length, extra)
            try:
                with target.open("rb") as handle:
                    handle.seek(start)
                    remaining = length
                    while remaining:
                        block = handle.read(min(256 * 1024, remaining))
                        if not block:
                            break
                        self.wfile.write(block)
                        remaining -= len(block)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _json(self, payload: Dict[str, object], status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(data))
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionResetError):
                return

        def _body(self) -> Dict[str, object]:
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError as exc:
                raise ValueError("invalid content length") from exc
            if length <= 0 or length > MAX_REQUEST_BYTES:
                raise ValueError("request body must be between 1 and 64000 bytes")
            try:
                value = json.loads(self.rfile.read(length))
            except json.JSONDecodeError as exc:
                raise ValueError("request body must be valid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError("request body must be an object")
            return value

        def _authorized_action(self) -> bool:
            if self.headers.get("X-TrendClip-Action") != "1":
                return False
            origin = self.headers.get("Origin")
            if not origin:
                return True
            parsed = urlparse(origin)
            return parsed.hostname in ("127.0.0.1", "localhost")

        def do_GET(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            if path == "/api/status":
                self._json(project_status(root))
                return
            if path.startswith("/media/"):
                relative = path.removeprefix("/media/")
                try:
                    target = ensure_within(root / "output" / relative, root / "output")
                except ValueError:
                    self._json({"error": "unsafe media path"}, 400)
                    return
                if not target.is_file() or target.suffix.lower() != ".mp4":
                    self._json({"error": "media not found"}, 404)
                    return
                self._serve_video(target)
                return
            static = {
                "/": dashboard_root / "index.html",
                "/app.js": dashboard_root / "app.js",
                "/styles.css": dashboard_root / "styles.css",
            }.get(path)
            if static and static.is_file():
                data = static.read_bytes()
                content_type = mimetypes.guess_type(static.name)[0] or "application/octet-stream"
                if content_type.startswith("text/") or content_type == "application/javascript":
                    content_type += "; charset=utf-8"
                self._headers(200, content_type, len(data))
                self.wfile.write(data)
                return
            self._json({"error": "not found"}, 404)

        def do_HEAD(self) -> None:  # noqa: N802
            path = unquote(urlparse(self.path).path)
            static = {
                "/": dashboard_root / "index.html",
                "/app.js": dashboard_root / "app.js",
                "/styles.css": dashboard_root / "styles.css",
            }.get(path)
            if static and static.is_file():
                content_type = mimetypes.guess_type(static.name)[0] or "application/octet-stream"
                if content_type.startswith("text/") or content_type == "application/javascript":
                    content_type += "; charset=utf-8"
                self._headers(200, content_type, static.stat().st_size)
                return
            self._headers(404, "application/json; charset=utf-8", 0)

        def do_POST(self) -> None:  # noqa: N802
            if not self._authorized_action():
                self._json({"error": "local action header required"}, 403)
                return
            try:
                body = self._body()
                if self.path == "/api/discover":
                    self._discover(body)
                elif self.path == "/api/render":
                    self._render(body)
                elif self.path == "/api/generate-candidate":
                    self._generate_candidate(body)
                elif self.path == "/api/analyze-source":
                    self._analyze_source(body)
                elif self.path == "/api/render-source-clip":
                    self._render_source_clip(body)
                elif self.path == "/api/track-upload":
                    self._track_upload(body)
                elif self.path == "/api/settings":
                    self._settings(body)
                elif self.path == "/api/test-codex":
                    self._test_codex()
                elif self.path == "/api/manual-source":
                    self._manual_source(body)
                elif self.path == "/api/cancel-job":
                    self._cancel_job(body)
                else:
                    self._json({"error": "not found"}, 404)
            except (ValueError, ConfigError, DiscoveryError, MediaPipelineError, ProfileError, RightsError) as exc:
                _log_event(root, "request-error", f"{self.path}: {exc}", "error")
                self._json({"error": str(exc)}, 400)

        def _discover(self, body: Dict[str, object]) -> None:
            topic = validate_slug(str(body.get("topic", "")))
            _log_event(root, "discovery-start", topic)
            profiles_path = root / "config" / "profiles.json"
            if profiles_path.is_file():
                profile = load_profile(profiles_path, topic)
                report = discover_youtube_profile(profile, query=str(body.get("query") or profile.query))
            else:
                topic_config = load_topic(root / "config" / "topics" / f"{topic}.json")
                report = discover_with_trends(topic_config, root / "config" / "sources" / f"{topic}.json")
            report_path = root / "state" / "discovery" / topic / "latest.json"
            report = _save_discovery_safely(report, report_path)
            _log_event(root, "discovery-complete", f"{topic}: {report['candidate_count']} candidates")
            self._json({"ok": True, "report": report})

        def _manual_source(self, body: Dict[str, object]) -> None:
            topic = validate_slug(str(body.get("topic", "")))
            profile = load_profile(root / "config" / "profiles.json", topic)
            candidate = inspect_youtube_url(profile, str(body.get("url", "")))
            report_path = root / "state" / "discovery" / topic / "latest.json"
            report = _read_json(report_path, {"topic": topic, "generated_at": datetime.now(timezone.utc).isoformat(), "candidates": [], "source_errors": [], "measurement_limits": "Manual source"})
            report["candidates"] = [candidate] + [item for item in report.get("candidates", []) if item.get("url") != candidate["url"]]
            report["candidate_count"] = len(report["candidates"])
            save_report(report, report_path)
            self._json({"ok": True, "candidate": candidate, "report": report})

        def _render(self, body: Dict[str, object]) -> None:
            topic = validate_slug(str(body.get("topic", "")))
            output_date = validate_date(str(body.get("date", "")))
            command = [
                sys.executable,
                "-m",
                "trendclip",
                "render",
                "--topic",
                topic,
                "--mode",
                "original",
                "--date",
                output_date,
            ]
            completed = subprocess.run(command, cwd=root, capture_output=True, text=True, timeout=240)
            if completed.returncode != 0:
                self._json(
                    {"ok": False, "error": completed.stderr.strip() or completed.stdout.strip()},
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                )
                return
            self._json({"ok": True, "status": project_status(root), "log": completed.stdout.strip()})

        def _generate_candidate(self, body: Dict[str, object]) -> None:
            topic = validate_slug(str(body.get("topic", "")))
            output_date = validate_date(str(body.get("date", "")))
            candidate_url = str(body.get("candidate_url", ""))
            report = _read_json(root / "state" / "discovery" / topic / "latest.json", {})
            candidate = next(
                (item for item in report.get("candidates", []) if item.get("url") == candidate_url),
                None,
            )
            if candidate is None:
                raise ValueError("select a candidate from the latest discovery report")
            try:
                result = render_candidate(root, topic, candidate, output_date)
            except RuntimeError as exc:
                self._json({"ok": False, "error": str(exc)}, HTTPStatus.UNPROCESSABLE_ENTITY)
                return
            self._json({"ok": True, "result": result, "status": project_status(root)})

        def _analyze_source(self, body: Dict[str, object]) -> None:
            topic = validate_slug(str(body.get("topic", "")))
            candidate_url = str(body.get("candidate_url", ""))
            report = _read_json(root / "state" / "discovery" / topic / "latest.json", {})
            if not any(item.get("url") == candidate_url for item in report.get("candidates", [])):
                raise ValueError("select a source from the latest discovery report")
            rights = validate_rights(body.get("rights"), require_reuse=True)
            profile = load_profile(root / "config" / "profiles.json", topic) if (root / "config" / "profiles.json").is_file() else None
            strategy = profile.strategy if profile else "gaming"
            job_id = job_id_for_url(candidate_url)
            update_job(root, job_id, stage="queued", message="Analysis requested", profile=topic, strategy=strategy)
            arguments = [
                "analyze", "--url", candidate_url, "--max-minutes", str(int(body.get("max_minutes", 90))),
                "--strategy", strategy, "--rights-json", json.dumps(rights, ensure_ascii=False),
            ]
            if body.get("use_browser_cookies") is True:
                arguments.append("--use-browser-cookies")
                _log_event(root, "browser-auth-enabled", "Chrome YouTube session enabled for one media job")
            try:
                analysis = _run_media_worker(root, arguments)
            except MediaPipelineError as exc:
                current = read_job(root, job_id) or {}
                if current.get("stage") != "cancelled":
                    update_job(root, job_id, stage="failed", message=str(exc))
                if "requires sign-in" in str(exc):
                    for item in report.get("candidates", []):
                        if item.get("url") == candidate_url:
                            item["availability"] = "requires-sign-in"
                    save_report(report, root / "state" / "discovery" / topic / "latest.json")
                raise
            for item in report.get("candidates", []):
                if item.get("url") == candidate_url:
                    item.pop("availability", None)
            save_report(report, root / "state" / "discovery" / topic / "latest.json")
            self._json({"ok": True, "analysis": analysis, "status": project_status(root)})

        def _render_source_clip(self, body: Dict[str, object]) -> None:
            job_id = str(body.get("job_id", ""))
            raw_destinations = body.get("destinations", [])
            if not isinstance(raw_destinations, list):
                raise ValueError("destinations must be a list")
            destinations = [str(item) for item in raw_destinations if str(item) in PLATFORMS]
            if not destinations:
                raise ValueError("choose at least one publishing destination")
            try:
                result = _run_media_worker(root, [
                "render",
                "--job-id", job_id,
                "--pick", str(int(body.get("pick", 0))),
                "--topic", validate_slug(str(body.get("topic", ""))),
                "--date", validate_date(str(body.get("date", ""))),
                "--hook", str(body.get("hook", "")),
                "--draft-kind", str(body.get("draft_kind", "best-story")),
                "--layout", str(body.get("layout", "balanced")),
                "--destinations", ",".join(destinations),
                ])
            except MediaPipelineError as exc:
                current = read_job(root, job_id) or {}
                if current.get("stage") != "cancelled":
                    update_job(root, job_id, stage="failed", message=str(exc))
                raise
            self._json({"ok": True, "result": result, "status": project_status(root)})

        def _track_upload(self, body: Dict[str, object]) -> None:
            platform = str(body.get("platform", "")).lower()
            topic = validate_slug(str(body.get("topic", "")))
            output_date = validate_date(str(body.get("date", "")))
            if platform not in PLATFORMS:
                raise ValueError("platform must be youtube, facebook, or tiktok")
            video = root / "output" / topic / output_date / "clip-001.mp4"
            if not video.is_file():
                raise ValueError("validated local video does not exist")
            tracking_path = root / "state" / "tracking.json"
            tracking = _read_json(tracking_path, {"records": []})
            tracking.setdefault("records", []).append(
                {
                    "platform": platform,
                    "topic": topic,
                    "date": output_date,
                    "status": "uploaded-manually",
                    "recorded_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            _atomic_json(tracking_path, tracking)
            self._json({"ok": True, "tracking": tracking})

        def _settings(self, body: Dict[str, object]) -> None:
            codex_enabled = body.get("codex_enabled")
            if not isinstance(codex_enabled, bool):
                raise ValueError("codex_enabled must be true or false")
            path = root / "config" / "settings.json"
            settings = _read_json(path, {})
            settings.setdefault("schema_version", 1)
            settings.setdefault("browser_session", {"enabled": False, "browser": "chrome"})
            settings.setdefault("publishing", {"mode": "manual-only"})
            settings.setdefault("codex", {})["enabled"] = codex_enabled
            settings["codex"].setdefault("timeout_seconds", 120)
            settings["codex"].setdefault("max_output_bytes", 262144)
            settings["codex"].setdefault("max_concurrency", 1)
            _atomic_json(path, settings)
            _log_event(root, "settings-change", f"codex_enabled={codex_enabled}")
            self._json({"ok": True, "status": project_status(root)})

        def _test_codex(self) -> None:
            try:
                result = codex_smoke_test(root)
            except CodexAdapterError as exc:
                raise ValueError(str(exc)) from exc
            _log_event(root, "codex-smoke-test", "Bounded synthetic semantic ranking passed")
            self._json({"ok": True, "result": result})

        def _cancel_job(self, body: Dict[str, object]) -> None:
            job_id = str(body.get("job_id", ""))
            if not re.fullmatch(r"[a-f0-9]{12}", job_id):
                raise ValueError("invalid media job")
            with WORKERS_LOCK:
                process = ACTIVE_WORKERS.get(job_id)
            if process is None or process.poll() is not None:
                raise ValueError("job is not currently running")
            _terminate_worker(process)
            update_job(root, job_id, stage="cancelled", message="Cancelled by the user; cached artifacts are retained for retry")
            _log_event(root, "media-worker-cancelled", f"job_id={job_id}")
            self._json({"ok": True, "status": project_status(root)})

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def refresh_discovery(root: Path) -> Dict[str, str]:
    results = {}
    profiles_path = root / "config" / "profiles.json"
    if profiles_path.is_file():
        for profile in load_profiles(profiles_path):
            try:
                report = discover_youtube_profile(profile)
                report = _save_discovery_safely(report, root / "state" / "discovery" / profile.slug / "latest.json")
                results[profile.slug] = f"{report['candidate_count']} candidates"
                _log_event(root, "discovery-complete", f"{profile.slug}: {report['candidate_count']} candidates")
            except (DiscoveryError, OSError) as exc:
                results[profile.slug] = f"using prior report: {exc}"
                _log_event(root, "discovery-error", f"{profile.slug}: {exc}", "error")
        return results
    for topic_path in sorted((root / "config" / "topics").glob("*.json")):
        topic = topic_path.stem
        source_path = root / "config" / "sources" / f"{topic}.json"
        if not source_path.is_file():
            continue
        try:
            report = discover_with_trends(load_topic(topic_path), source_path)
            report = _save_discovery_safely(report, root / "state" / "discovery" / topic / "latest.json")
            results[topic] = f"{report['candidate_count']} candidates"
            _log_event(root, "discovery-complete", f"{topic}: {report['candidate_count']} candidates")
        except (ConfigError, DiscoveryError, OSError) as exc:
            results[topic] = f"using prior report: {exc}"
            _log_event(root, "discovery-error", f"{topic}: {exc}", "error")
    return results


def serve_dashboard(
    root: Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    refresh: bool = True,
    open_browser: bool = False,
) -> None:
    if host not in ("127.0.0.1", "localhost"):
        raise ValueError("dashboard may only bind to the loopback interface")
    server = ThreadingHTTPServer((host, port), make_handler(root))
    studio_url = f"http://{host}:{port}"
    _log_event(root, "studio-start", f"version=0.5.0 address={studio_url}")
    print(f"TrendClip Studio dashboard: {studio_url}", flush=True)
    print("Publishing is disabled; press Ctrl+C to stop.", flush=True)
    if open_browser:
        try:
            if not webbrowser.open(studio_url):
                raise RuntimeError("no browser handler")
        except (OSError, RuntimeError, webbrowser.Error):
            print(f"Browser could not be opened automatically. Open {studio_url}", flush=True)
    if refresh:
        def refresh_in_background():
            profiles_path = root / "config" / "profiles.json"
            if profiles_path.is_file():
                profile = load_profiles(profiles_path)[0]
                _log_event(root, "discovery-start", f"automatic startup refresh: {profile.slug}")
                try:
                    report = discover_youtube_profile(profile)
                    report = _save_discovery_safely(report, root / "state" / "discovery" / profile.slug / "latest.json")
                    _log_event(root, "discovery-complete", f"{profile.slug}: {report['candidate_count']} candidates")
                    print(f"Discovery {profile.slug}: {report['candidate_count']} candidates", flush=True)
                except (DiscoveryError, OSError) as exc:
                    _log_event(root, "discovery-error", f"{profile.slug}: {exc}", "error")
                return
            for topic, result in refresh_discovery(root).items():
                print(f"Discovery {topic}: {result}", flush=True)

        threading.Thread(target=refresh_in_background, name="trendclip-discovery", daemon=True).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

