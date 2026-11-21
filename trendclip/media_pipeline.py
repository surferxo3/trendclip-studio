"""Authorized source ingestion, moment detection, transcription, and vertical clipping."""

from __future__ import annotations

import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

from .config import validate_date, validate_slug
from .validate import add_content_quality, inspect_media_quality, probe_video, write_validation
from .highlight_strategies import select_moments
from .drafts import editorial_summary
from .jobs import update_job
from .rights import validate_rights


ALLOWED_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
HYPE = re.compile(r"\b(no way|oh my god|omg|what|wait|bro|let'?s go|holy|insane|crazy|yo+|wtf|dude|look at)\b", re.I)
SLURS = re.compile(r"\b(nigg\w*|n[i1]gg?a\w*|f[a@]gg?\w*|retard\w*|tranny\w*|chink\w*|spic\w*|kike\w*)\b", re.I)
SWEARS = re.compile(r"\b(fuck\w*|motherfuck\w*|shit\w*|bitch\w*|cunt\w*|dick\w*|pussy\w*|asshole\w*|whore\w*)\b", re.I)
RENDER_LAYOUTS = {"balanced", "punch", "clean"}


class MediaPipelineError(RuntimeError):
    """A safe, user-facing media pipeline failure."""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _run(command: List[str], *, timeout: int = 900) -> subprocess.CompletedProcess:
    try:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise MediaPipelineError(f"media command could not complete: {exc}") from exc
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "media command failed")[-1800:].strip()
        using_browser_session = "--cookies-from-browser" in command
        if "Sign in to confirm you’re not a bot" in message or "Sign in to confirm you're not a bot" in message:
            if using_browser_session:
                raise MediaPipelineError(
                    "YouTube did not accept the current Chrome session. Open YouTube in Chrome, confirm you are signed in, then try again."
                )
            raise MediaPipelineError(
                "YouTube requires sign-in for this video. Enable the Chrome YouTube session setting, or choose another source."
            )
        if using_browser_session and ("could not find chrome cookies" in message.lower() or "failed to decrypt" in message.lower()):
            raise MediaPipelineError(
                "TrendClip could not read the Chrome YouTube session. Open Chrome, sign in to YouTube, and try again."
            )
        if "Requested format is not available" in message:
            raise MediaPipelineError(
                "YouTube did not provide a downloadable video format for this source. Try again after updating Studio, or choose another source."
            )
        if "HTTP error 403" in message or "Server returned 403" in message:
            raise MediaPipelineError(
                "YouTube denied a temporary media link. Retry the source once; if it continues, enable the Chrome YouTube session or choose another source."
            )
        raise MediaPipelineError(message)
    return completed


def _validate_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise MediaPipelineError("source must be an HTTPS YouTube URL")
    return url


def job_id_for_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:12]


def _yt_dlp(*, use_browser_cookies: bool = False) -> List[str]:
    command = [sys.executable, "-m", "yt_dlp", "--no-warnings", "--no-progress", "--no-playlist"]
    node = shutil.which("node")
    if node:
        command += ["--js-runtimes", f"node:{node}"]
    if use_browser_cookies:
        command += ["--cookies-from-browser", "chrome"]
    return command


def _download_analysis_audio(
    ytdlp: List[str],
    url: str,
    job: Path,
    limit_seconds: float,
    *,
    section_limited: bool = True,
) -> Path:
    """Download only audio for the full-source analysis pass."""
    template = job / "analysis-audio.%(ext)s"
    command = ytdlp + ["-f", "ba/b", "-o", str(template)]
    if section_limited and limit_seconds > 0:
        command += ["--download-sections", f"*0-{limit_seconds:.3f}"]
    _run(command + [url], timeout=1800)
    downloaded = next(
        (path for path in job.glob("analysis-audio.*") if path.suffix not in {".part", ".ytdl"} and path.is_file() and path.stat().st_size > 0),
        None,
    )
    if downloaded is None:
        raise MediaPipelineError("the source audio was not downloaded")
    return downloaded


def _download_analysis_proxy(
    ytdlp: List[str],
    url: str,
    job: Path,
    limit_seconds: float,
    *,
    section_limited: bool = True,
) -> Optional[Path]:
    """Best-effort low-resolution video used only for motion/shot signals."""
    template = job / "analysis-proxy.%(ext)s"
    command = ytdlp + ["-f", "bv*[height<=240]/wv*", "-o", str(template)]
    if section_limited and limit_seconds > 0:
        command += ["--download-sections", f"*0-{limit_seconds:.3f}"]
    try:
        _run(command + [url], timeout=1800)
    except MediaPipelineError:
        return None
    return next(
        (path for path in job.glob("analysis-proxy.*") if path.suffix not in {".part", ".ytdl"} and path.is_file() and path.stat().st_size > 0),
        None,
    )


def _download_render_section(info: Dict[str, object], candidate: Dict[str, object], destination: Path) -> float:
    """Download only the selected video range and return its source-time offset."""
    start = max(0.0, float(candidate["start"]) - 2.0)
    end = min(float(info["duration"]), float(candidate["end"]) + 2.0)
    if destination.is_file() and destination.stat().st_size > 0:
        return start
    ytdlp = _yt_dlp(use_browser_cookies=info.get("authentication") == "chrome-browser-session")
    command = ytdlp + [
        "-f", "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]/b",
        "--merge-output-format", "mp4",
        "--download-sections", f"*{start:.3f}-{end:.3f}",
        "--force-keyframes-at-cuts",
        "-o", str(destination),
        str(info["source_url"]),
    ]
    _run(command, timeout=1800)
    if not destination.is_file() or destination.stat().st_size == 0:
        raise MediaPipelineError("the selected source section was not downloaded")
    return start


def ingest_source(
    root: Path,
    url: str,
    *,
    rights_confirmed: bool = False,
    rights: Optional[Dict[str, object]] = None,
    max_minutes: int = 90,
    use_browser_cookies: bool = False,
) -> Dict[str, object]:
    """Download a selected YouTube source into a deterministic local review job."""
    try:
        rights_record = validate_rights(rights, require_reuse=True) if rights is not None else validate_rights({"category": "creator-owned", "allowed_platforms": ["youtube", "facebook", "tiktok"], "commercial_use_scope": "unknown", "attribution_required": False}, require_reuse=True) if rights_confirmed else None
    except ValueError as exc:
        raise MediaPipelineError(str(exc)) from exc
    if rights_record is None:
        raise MediaPipelineError("source provenance is required before download")
    url = _validate_url(url)
    if not 1 <= max_minutes <= 90:
        raise MediaPipelineError("analysis limit must be between 1 and 90 minutes")
    job_id = job_id_for_url(url)
    job = root / "state" / "jobs" / job_id
    job.mkdir(parents=True, exist_ok=True)
    update_job(root, job_id, stage="ingesting", message="Checking source metadata", source_url=url)
    _write_json(job / "rights.json", rights_record)
    source = job / "source.mp4"
    audio = job / "audio.wav"
    cached_info = job / "info.json"
    if cached_info.is_file() and ((audio.is_file() and audio.stat().st_size > 0) or (source.is_file() and source.stat().st_size > 0)):
        info = _read_json(cached_info)
        info["rights_confirmed"] = True
        info["rights"] = rights_record
        info["cache_reused"] = True
        _write_json(cached_info, info)
        update_job(root, job_id, stage="transcribing", message="Using cached source")
        return info
    ytdlp = _yt_dlp(use_browser_cookies=use_browser_cookies)
    info_result = _run(ytdlp + ["--skip-download", "--dump-single-json", url], timeout=120)
    try:
        raw = json.loads(info_result.stdout)
    except json.JSONDecodeError as exc:
        raise MediaPipelineError("YouTube returned unreadable video metadata") from exc
    duration = float(raw.get("duration") or 0)
    if duration <= 0:
        raise MediaPipelineError("the selected source has no usable duration")
    if raw.get("is_live"):
        raise MediaPipelineError("live recording uses a separate workflow and is not enabled in Studio yet")
    analysis_duration = min(duration, max_minutes * 60)
    section_limited = analysis_duration + .01 < duration
    downloaded_audio = _download_analysis_audio(
        ytdlp,
        url,
        job,
        analysis_duration,
        section_limited=section_limited,
    )
    _extract_audio(downloaded_audio, audio)
    if downloaded_audio != audio:
        downloaded_audio.unlink(missing_ok=True)
    if not audio.is_file() or audio.stat().st_size == 0:
        raise MediaPipelineError("the analysis audio could not be prepared")
    update_job(root, job_id, stage="analyzing", message="Preparing a small visual proxy for motion and shot signals")
    analysis_proxy = _download_analysis_proxy(
        ytdlp,
        url,
        job,
        analysis_duration,
        section_limited=section_limited,
    )
    info = {
        "job_id": job_id,
        "title": raw.get("title") or "Untitled source",
        "channel": raw.get("channel") or raw.get("uploader") or "Unknown channel",
        "source_url": raw.get("webpage_url") or url,
        "duration": analysis_duration,
        "view_count": raw.get("view_count"),
        "heatmap": raw.get("heatmap") or [],
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "rights_confirmed": True,
        "rights": rights_record,
        "authentication": "chrome-browser-session" if use_browser_cookies else "anonymous",
        "analysis_mode": "audio-plus-low-resolution-visual-proxy" if analysis_proxy else "audio-first-fallback",
        "audio_file": str(audio),
        "visual_proxy_file": str(analysis_proxy) if analysis_proxy else None,
        "video_download": "deferred-until-draft-selection",
    }
    _write_json(job / "info.json", info)
    update_job(root, job_id, stage="transcribing", message="Analysis audio downloaded; full video deferred until draft selection")
    return info


def _extract_audio(source: Path, audio: Path) -> None:
    if audio.is_file():
        return
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(source), "-ac", "1", "-ar", "16000", str(audio)])


def _transcribe(audio: Path, transcript_path: Path, model_name: str) -> List[Dict[str, object]]:
    if transcript_path.is_file():
        return _read_json(transcript_path)
    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise MediaPipelineError("media dependencies are missing; start Studio with the project launcher") from exc
    with wave.open(str(audio)) as handle:
        pcm = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments, _ = model.transcribe(pcm, word_timestamps=True, vad_filter=True)
        words = [
            {"w": word.word.strip(), "s": round(word.start, 2), "e": round(word.end, 2)}
            for segment in segments
            for word in (segment.words or [])
            if word.word.strip()
        ]
    except Exception as exc:
        raise MediaPipelineError(f"transcription failed: {exc}") from exc
    _write_json(transcript_path, words)
    return words


def _visual_signals(source: Path, destination: Path, duration: float) -> List[Dict[str, object]]:
    """Cache lightweight frame-difference samples; this is not semantic vision analysis."""
    if destination.is_file():
        return _read_json(destination)
    try:
        import cv2
        import numpy as np
    except ImportError as exc:
        raise MediaPipelineError("OpenCV and NumPy are required for visual-change analysis") from exc
    capture = cv2.VideoCapture(str(source))
    step = max(1, int(math.ceil(duration / 3600)))
    previous = None
    signals = []
    try:
        for second in range(0, int(duration), step):
            capture.set(cv2.CAP_PROP_POS_MSEC, second * 1000)
            ok, frame = capture.read()
            if not ok:
                continue
            gray = cv2.resize(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY), (160, 90))
            motion = 0.0 if previous is None else float(np.mean(cv2.absdiff(gray, previous)) / 255.0)
            signals.append({"second": second, "motion": round(motion, 5)})
            previous = gray
    finally:
        capture.release()
    _write_json(destination, signals)
    return signals


def _smooth(values, width: int):
    import numpy as np
    width = min(len(values), max(1, width))
    return np.convolve(values, np.ones(width) / width, mode="same")


def _z(values):
    import numpy as np
    values = np.asarray(values, dtype=float)
    if values.std() < 1e-9:
        return np.zeros_like(values)
    return (values - np.median(values)) / (values.std() + 1e-9)


def score_moments(words, db, heatmap, duration: float, *, top: int = 8, minimum: float = 15, maximum: float = 30):
    """Rank non-overlapping candidate windows using energy, speech, and replay data."""
    import numpy as np
    count = len(db)
    loud = _smooth(np.clip(_z(db - _smooth(db, 30)), 0, None), 3)
    hype = np.zeros(count)
    speech = np.zeros(count)
    for word in words:
        second = int(float(word["s"]))
        if 0 <= second < count:
            speech[second] += 1
            if HYPE.search(str(word["w"])):
                hype[second] += 1
    hype = _smooth(hype, 5)
    heat = np.zeros(count)
    for entry in heatmap or []:
        start = max(0, int(entry.get("start_time", 0)))
        end = min(count, int(math.ceil(entry.get("end_time", start))))
        heat[start:end] = float(entry.get("value", 0))
    score = loud + 0.8 * np.clip(_z(hype), 0, None) + 2.0 * np.clip(_z(heat), 0, None) if heat.any() else loud + 0.8 * np.clip(_z(hype), 0, None)
    score += 0.15 * np.clip(_z(_smooth(speech, 5)), 0, None)
    used = np.zeros(count, dtype=bool)
    picks = []
    for peak in np.argsort(-score):
        if len(picks) >= top or score[peak] <= 0:
            break
        start = max(0.0, float(peak) - maximum * 0.45)
        end = min(duration, start + maximum)
        segment_words = [word for word in words if start <= float(word["s"]) < end]
        if segment_words:
            start = max(0.0, float(segment_words[0]["s"]) - 0.25)
            end = min(duration, max(start + minimum, float(segment_words[-1]["e"]) + 0.5), start + maximum)
        if end - start < minimum:
            continue
        if used[int(start):max(int(start) + 1, int(end))].any():
            continue
        used[int(start):max(int(start) + 1, int(end))] = True
        text = " ".join(str(word["w"]) for word in words if start <= float(word["s"]) < end)
        why = []
        if loud[peak] > 1:
            why.append("audio energy spike")
        if hype[peak] > 0:
            why.append("hype language")
        if heat.any() and heat[peak] > 0.5:
            why.append("YouTube most-replayed signal")
        picks.append({
            "n": len(picks) + 1,
            "start": round(start, 2),
            "end": round(end, 2),
            "duration": round(end - start, 2),
            "score": round(float(score[peak]), 2),
            "why": why or ["overall audio and speech energy"],
            "text": text[:500],
        })
    return sorted(picks, key=lambda item: item["score"], reverse=True)


def analyze_source(root: Path, job_id: str, *, model_name: str = "small", strategy: str = "gaming") -> Dict[str, object]:
    if not re.fullmatch(r"[a-f0-9]{12}", job_id):
        raise MediaPipelineError("invalid media job")
    job = root / "state" / "jobs" / job_id
    update_job(root, job_id, stage="transcribing", message="Extracting audio and transcribing speech", strategy=strategy)
    info = _read_json(job / "info.json")
    source = job / "source.mp4"
    proxy_value = info.get("visual_proxy_file")
    visual_source = source
    if proxy_value:
        proxy_path = Path(str(proxy_value)).resolve()
        try:
            proxy_path.relative_to(job.resolve())
        except ValueError:
            proxy_path = source
        visual_source = proxy_path
    audio = job / "audio.wav"
    if not audio.is_file():
        if not source.is_file():
            raise MediaPipelineError("analysis audio is missing; retry the source download")
        _extract_audio(source, audio)
    try:
        import numpy as np
    except ImportError as exc:
        raise MediaPipelineError("NumPy is not installed") from exc
    with wave.open(str(audio)) as handle:
        samples = np.frombuffer(handle.readframes(handle.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    seconds = len(samples) // 16000
    if seconds < 7:
        raise MediaPipelineError("source must be at least 7 seconds long")
    frames = samples[: seconds * 16000].reshape(seconds, 16000)
    db = 20 * np.log10(np.sqrt((frames ** 2).mean(1) + 1e-9))
    words = _transcribe(audio, job / "transcript.json", model_name)
    media_duration = min(float(info["duration"]), len(samples) / 16000)
    visual_signals = _visual_signals(visual_source, job / "visual-signals.json", media_duration) if visual_source.is_file() else []
    minimum = min(15.0, max(7.0, media_duration - 0.1))
    maximum = min(30.0, media_duration)
    update_job(root, job_id, stage="analyzing", message=f"Scoring moments with the {strategy} strategy")
    candidates = select_moments(strategy, words, db, info.get("heatmap"), media_duration, visual_signals=visual_signals, minimum=minimum, maximum=maximum)
    if not candidates:
        fallback_duration = min(30.0, media_duration)
        candidates = [{"n": 1, "start": 0.0, "end": fallback_duration, "duration": fallback_duration, "score": 0.0, "quality_score": 0.0, "score_components": {}, "quality_components": {"clean_start": 0.0, "clean_end": 0.0, "hook": 0.0, "payoff": 0.0, "gaming_event": 0.0}, "why": ["opening segment fallback"], "warnings": ["no meaningful signal peak was found"], "text": " ".join(str(word["w"]) for word in words[:80])}]
    editorial = editorial_summary(candidates)
    result = {"job_id": job_id, "info": info, "strategy": strategy, "candidates": candidates, **editorial, "signals": {"words": len(words), "heatmap": bool(info.get("heatmap")), "loudness": True, "visual_change_samples": len(visual_signals), "analysis_mode": info.get("analysis_mode", "full-video-legacy")}}
    _write_json(job / "analysis.json", result)
    _write_json(root / "state" / "media" / "latest.json", result)
    update_job(root, job_id, stage="ready", message=str(editorial["editorial_message"]))
    return result


def _clean_word(value: str) -> str:
    def mask(match):
        word = match.group(0)
        return word[0] + "*" * (len(word) - 1)
    return SWEARS.sub(mask, SLURS.sub(mask, value))


def _ass_time(value: float) -> str:
    value = max(0.0, value)
    return f"{int(value // 3600)}:{int(value % 3600 // 60):02d}:{value % 60:05.2f}"


def _write_captions(words, start: float, end: float, hook: str, destination: Path) -> None:
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Arial,88,&H00FFFFFF,&H0000E5FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,7,3,5,60,60,0,1
Style: Hook,Arial,66,&H00000000,&H00000000,&H00FFFFFF,&H00FFFFFF,-1,0,0,0,100,100,0,0,3,18,0,8,70,70,160,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    selected = [word for word in words if start <= float(word["s"]) < end]
    events = []
    for index in range(0, len(selected), 3):
        group = selected[index:index + 3]
        if not group:
            continue
        group_end = min(end, float(group[-1]["e"]) + 0.45)
        for active, word in enumerate(group):
            begin = float(word["s"]) - start
            finish = (float(group[active + 1]["s"]) - start) if active + 1 < len(group) else group_end - start
            parts = []
            for position, item in enumerate(group):
                text = _clean_word(str(item["w"])).upper().replace("{", "(").replace("}", ")")
                parts.append("{\\c&H0000E5FF&}" + text + "{\\c&H00FFFFFF&}" if position == active else text)
            events.append(f"Dialogue: 0,{_ass_time(begin)},{_ass_time(finish)},Cap,,0,0,0,,{{\\pos(540,1420)}}{' '.join(parts)}")
    if hook.strip():
        safe_hook = hook.replace("{", "(").replace("}", ")").replace("\n", " ")[:100]
        events.append(f"Dialogue: 1,0:00:00.00,0:00:02.80,Hook,,0,0,0,,{safe_hook}")
    destination.write_text(header + "\n".join(events) + "\n", encoding="utf-8")


def _ascii(value: str) -> str:
    return value.encode("ascii", "ignore").decode("ascii").strip()


def _caption_groups(words, start: float, end: float):
    selected = [word for word in words if start <= float(word["s"]) < end]
    return [selected[index:index + 3] for index in range(0, len(selected), 3)]


def _draw_centered_words(frame, group, active: int, y: int, *, accent=(0, 229, 255), scale: float = 2.0) -> None:
    import cv2
    font = cv2.FONT_HERSHEY_DUPLEX
    thickness, gap = 4, 24
    values = [_ascii(_clean_word(str(item["w"]))).upper() for item in group]
    values = [value for value in values if value]
    if not values:
        return
    sizes = [cv2.getTextSize(value, font, scale, thickness)[0] for value in values]
    total = sum(size[0] for size in sizes) + gap * (len(values) - 1)
    x = max(35, (1080 - total) // 2)
    for index, (value, size) in enumerate(zip(values, sizes)):
        cv2.putText(frame, value, (x, y), font, scale, (0, 0, 0), 12, cv2.LINE_AA)
        color = accent if index == active else (255, 255, 255)
        cv2.putText(frame, value, (x, y), font, scale, color, thickness, cv2.LINE_AA)
        x += size[0] + gap


def _draw_hook(frame, hook: str, *, layout: str = "balanced") -> None:
    import cv2
    text = _ascii(hook).upper()[:80]
    if not text:
        return
    words, lines, current = text.split(), [], ""
    for word in words:
        proposed = f"{current} {word}".strip()
        if len(proposed) > 27 and current:
            lines.append(current)
            current = word
        else:
            current = proposed
    if current:
        lines.append(current)
    lines = lines[:2]
    top = 105
    height = 82 * len(lines) + 42
    background = (255, 255, 255) if layout != "punch" else (24, 218, 255)
    foreground = (0, 0, 0) if layout != "clean" else (20, 24, 30)
    cv2.rectangle(frame, (55, top), (1025, top + height), background, -1)
    for index, line in enumerate(lines):
        size = cv2.getTextSize(line, cv2.FONT_HERSHEY_DUPLEX, 1.65, 4)[0]
        cv2.putText(frame, line, ((1080 - size[0]) // 2, top + 72 + index * 78), cv2.FONT_HERSHEY_DUPLEX, 1.65, foreground, 4, cv2.LINE_AA)


def _persistent_portrait_crop(frames) -> Dict[str, object]:
    """Detect a stable central portrait region without semantic vision.

    The detector intentionally handles only strong evidence: repeated activity in
    a 9:16-shaped central band with substantially quieter side columns. Mixed or
    ambiguous footage falls back to the requested layout rather than jittering a
    crop from frame to frame.
    """
    if not frames:
        return {"mode": "layout-fallback", "confidence": 0.0, "crop": None, "samples": 0}
    import cv2
    import numpy as np
    base_height, base_width = frames[0].shape[:2]
    if base_height < 2 or base_width < 2:
        return {"mode": "layout-fallback", "confidence": 0.0, "crop": None, "samples": len(frames)}
    if base_width / base_height <= .70:
        return {"mode": "native-portrait", "confidence": 1.0, "crop": [0.0, 0.0, 1.0, 1.0], "samples": len(frames)}
    crop_width = min(base_width, max(2, int(round(base_height * 9 / 16))))
    search_margin = max(1, int(base_width * .18))
    candidates = []
    contrasts = []
    for raw in frames:
        frame = raw if raw.shape[:2] == (base_height, base_width) else cv2.resize(raw, (base_width, base_height))
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        y0, y1 = int(base_height * .08), max(int(base_height * .92), int(base_height * .08) + 2)
        region = gray[y0:y1].astype(np.float32)
        spread = np.percentile(region, 90, axis=0) - np.percentile(region, 10, axis=0)
        deviation = region.std(axis=0)
        activity = spread * .65 + deviation * .35
        kernel_width = max(5, base_width // 100)
        smoothed = np.convolve(activity, np.ones(kernel_width) / kernel_width, mode="same")
        window = np.convolve(smoothed, np.ones(crop_width), mode="valid")
        expected_start = (base_width - crop_width) // 2
        low = max(0, expected_start - search_margin)
        high = min(len(window), expected_start + search_margin + 1)
        if high <= low:
            continue
        start = low + int(np.argmax(window[low:high]))
        end = start + crop_width
        inside = float(smoothed[start:end].mean())
        outside_values = np.concatenate((smoothed[:start], smoothed[end:]))
        outside = float(np.median(outside_values)) if len(outside_values) else inside
        contrast = inside / max(outside, 1.0)
        center_offset = abs((start + end) / 2 - base_width / 2) / base_width
        if inside >= 10.0 and contrast >= 1.9 and center_offset <= .16:
            candidates.append((start + end) / 2)
            contrasts.append(contrast)
    sample_count = len(frames)
    evidence_ratio = len(candidates) / sample_count
    if len(candidates) < 2 or evidence_ratio < .34:
        return {
            "mode": "layout-fallback",
            "confidence": round(evidence_ratio, 2),
            "crop": None,
            "samples": sample_count,
        }
    center = float(np.median(candidates))
    start = int(round(center - crop_width / 2))
    start = max(0, min(base_width - crop_width, start))
    contrast_strength = min(1.0, float(np.median(contrasts)) / 3.0)
    confidence = min(1.0, evidence_ratio * contrast_strength)
    return {
        "mode": "embedded-portrait",
        "confidence": round(confidence, 2),
        "crop": [round(start / base_width, 5), 0.0, round((start + crop_width) / base_width, 5), 1.0],
        "samples": sample_count,
    }


def _analyze_framing(source: Path, start: float, duration: float, *, sample_count: int = 9) -> Dict[str, object]:
    import cv2
    import numpy as np
    capture = cv2.VideoCapture(str(source))
    frames = []
    try:
        if duration <= 0:
            return {"mode": "layout-fallback", "confidence": 0.0, "crop": None, "samples": 0}
        inset = min(.35, duration * .05)
        for timestamp in np.linspace(start + inset, max(start + inset, start + duration - inset), max(1, sample_count)):
            capture.set(cv2.CAP_PROP_POS_MSEC, float(timestamp) * 1000)
            ok, frame = capture.read()
            if ok:
                frames.append(frame)
    finally:
        capture.release()
    return _persistent_portrait_crop(frames)


def _crop_frame(source_frame, crop):
    if not crop:
        return source_frame
    height, width = source_frame.shape[:2]
    x0 = max(0, min(width - 1, int(round(float(crop[0]) * width))))
    y0 = max(0, min(height - 1, int(round(float(crop[1]) * height))))
    x1 = max(x0 + 1, min(width, int(round(float(crop[2]) * width))))
    y1 = max(y0 + 1, min(height, int(round(float(crop[3]) * height))))
    return source_frame[y0:y1, x0:x1]


def _frame_supports_portrait_crop(source_frame, crop) -> bool:
    if not crop:
        return False
    import cv2
    import numpy as np
    height, width = source_frame.shape[:2]
    x0 = max(0, min(width - 1, int(round(float(crop[0]) * width))))
    x1 = max(x0 + 1, min(width, int(round(float(crop[2]) * width))))
    y0, y1 = int(height * .08), max(int(height * .92), int(height * .08) + 2)
    gray = cv2.cvtColor(source_frame, cv2.COLOR_BGR2GRAY)[y0:y1].astype(np.float32)
    spread = np.percentile(gray, 90, axis=0) - np.percentile(gray, 10, axis=0)
    deviation = gray.std(axis=0)
    activity = spread * .65 + deviation * .35
    kernel_width = max(5, width // 100)
    smoothed = np.convolve(activity, np.ones(kernel_width) / kernel_width, mode="same")
    inside = float(smoothed[x0:x1].mean())
    outside_values = np.concatenate((smoothed[:x0], smoothed[x1:]))
    outside = float(np.median(outside_values)) if len(outside_values) else inside
    return inside >= 10.0 and inside / max(outside, 1.0) >= 1.75


def _vertical_frame(source_frame, *, layout: str = "balanced", active_crop=None):
    import cv2
    focus_frame = _crop_frame(source_frame, active_crop)
    height, width = focus_frame.shape[:2]
    cover_source = focus_frame if active_crop else source_frame
    cover_height, cover_width = cover_source.shape[:2]
    cover_scale = max(1080 / cover_width, 1920 / cover_height)
    cover = cv2.resize(cover_source, (int(cover_width * cover_scale) + 2, int(cover_height * cover_scale) + 2))
    x0 = max(0, (cover.shape[1] - 1080) // 2)
    y0 = max(0, (cover.shape[0] - 1920) // 2)
    background = cover[y0:y0 + 1920, x0:x0 + 1080]
    if layout == "punch":
        # A full-height centre crop keeps action large and removes the blurred
        # canvas used by the balanced story treatment.
        return cv2.convertScaleAbs(background, alpha=1.06, beta=2)
    background = cv2.GaussianBlur(background, (0, 0), 26)
    background = cv2.convertScaleAbs(background, alpha=0.70, beta=-10)
    foreground_width = 940 if layout == "clean" else 1080
    foreground_height = max(2, int(height * foreground_width / width))
    foreground = cv2.resize(focus_frame, (foreground_width, foreground_height))
    maximum_foreground_height = (1720 if layout == "clean" else 1920) if active_crop else 1500
    if foreground_height > maximum_foreground_height:
        crop_y = (foreground_height - maximum_foreground_height) // 2
        foreground = foreground[crop_y:crop_y + maximum_foreground_height]
        foreground_height = foreground.shape[0]
    overlay_y = max(0 if active_crop else 210, (1920 - foreground_height) // 2)
    overlay_y = min(1920 - foreground_height, overlay_y)
    overlay_x = (1080 - foreground_width) // 2
    if layout == "clean":
        cv2.rectangle(background, (overlay_x - 8, overlay_y - 8), (overlay_x + foreground_width + 8, overlay_y + foreground_height + 8), (240, 240, 240), 8)
    background[overlay_y:overlay_y + foreground_height, overlay_x:overlay_x + foreground_width] = foreground
    return background


def _render_with_opencv(source: Path, destination: Path, words, candidate, hook: str, *, source_offset: float = 0.0, layout: str = "balanced") -> Dict[str, object]:
    try:
        import cv2
    except ImportError as exc:
        raise MediaPipelineError("OpenCV is not installed") from exc
    if layout not in RENDER_LAYOUTS:
        raise MediaPipelineError("unknown render layout")
    start, end = float(candidate["start"]), float(candidate["end"])
    duration = end - start
    local_start = max(0.0, start - source_offset)
    framing = _analyze_framing(source, local_start, duration)
    active_crop = framing.get("crop") if framing.get("mode") in {"embedded-portrait", "native-portrait"} else None
    adaptive_crop = framing.get("mode") == "embedded-portrait"
    crop_enabled = framing.get("mode") == "native-portrait"
    pending_crop_state = None
    pending_crop_frames = 0
    cropped_frame_count = 0
    frame_count = int(math.ceil(duration * 30))
    command = [
        "ffmpeg", "-y", "-v", "error",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", "1080x1920", "-r", "30", "-i", "pipe:0",
        "-ss", f"{local_start:.3f}", "-t", f"{duration:.3f}", "-i", str(source),
        "-map", "0:v", "-map", "1:a?", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-movflags", "+faststart", "-shortest", str(destination),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    capture = cv2.VideoCapture(str(source))
    groups = _caption_groups(words, start, end)
    try:
        for index in range(frame_count):
            absolute = start + index / 30
            capture.set(cv2.CAP_PROP_POS_MSEC, (local_start + index / 30) * 1000)
            ok, source_frame = capture.read()
            if not ok:
                break
            if adaptive_crop:
                supported = _frame_supports_portrait_crop(source_frame, active_crop)
                if index == 0:
                    crop_enabled = supported
                elif supported == crop_enabled:
                    pending_crop_state = None
                    pending_crop_frames = 0
                else:
                    if pending_crop_state != supported:
                        pending_crop_state = supported
                        pending_crop_frames = 1
                    else:
                        pending_crop_frames += 1
                    if pending_crop_frames >= 6:
                        crop_enabled = supported
                        pending_crop_state = None
                        pending_crop_frames = 0
            frame_crop = active_crop if crop_enabled else None
            if frame_crop:
                cropped_frame_count += 1
            frame = _vertical_frame(source_frame, layout=layout, active_crop=frame_crop)
            for group in groups:
                group_start = float(group[0]["s"])
                group_end = float(group[-1]["e"]) + 0.45
                if group_start <= absolute <= group_end:
                    active = 0
                    for position, word in enumerate(group):
                        if absolute >= float(word["s"]):
                            active = position
                    caption_y = 1510 if layout == "punch" else (1585 if layout == "clean" else 1480)
                    accent = (24, 218, 255) if layout == "punch" else ((255, 210, 70) if layout == "clean" else (0, 229, 255))
                    _draw_centered_words(frame, group, active, caption_y, accent=accent, scale=1.8 if layout == "clean" else 2.0)
                    break
            if index < 84:
                _draw_hook(frame, hook, layout=layout)
            assert process.stdin is not None
            process.stdin.write(frame.tobytes())
    except (BrokenPipeError, OSError) as exc:
        raise MediaPipelineError(f"video encoder stopped unexpectedly: {exc}") from exc
    finally:
        capture.release()
        if process.stdin:
            process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    code = process.wait()
    if code != 0:
        raise MediaPipelineError(stderr[-1800:].strip() or "video encoding failed")
    framing["application"] = "adaptive-with-hysteresis" if adaptive_crop else ("stable" if active_crop else "layout-fallback")
    framing["applied_frame_ratio"] = round(cropped_frame_count / max(frame_count, 1), 2)
    return framing


def render_candidate_clip(root: Path, job_id: str, pick_number: int, *, topic: str, output_date: str, hook: str = "", draft_kind: str = "best-story", layout: str = "balanced", destinations: Optional[List[str]] = None) -> Dict[str, object]:
    topic = validate_slug(topic)
    output_date = validate_date(output_date)
    if not re.fullmatch(r"[a-z0-9-]{1,32}", draft_kind):
        raise MediaPipelineError("invalid draft kind")
    if layout not in RENDER_LAYOUTS:
        raise MediaPipelineError("unknown render layout")
    selected_destinations = set(["youtube", "facebook", "tiktok"] if destinations is None else destinations)
    if not selected_destinations or not selected_destinations <= {"youtube", "facebook", "tiktok"}:
        raise MediaPipelineError("select at least one supported publishing destination")
    job = root / "state" / "jobs" / job_id
    analysis = _read_json(job / "analysis.json")
    candidate = next((item for item in analysis["candidates"] if int(item["n"]) == int(pick_number)), None)
    if not candidate:
        raise MediaPipelineError("select one of the analyzed moments")
    words = _read_json(job / "transcript.json")
    edits = job / "edits"
    edits.mkdir(exist_ok=True)
    legacy_source = job / "source.mp4"
    source = legacy_source
    source_offset = 0.0
    if not legacy_source.is_file():
        source = edits / f"source-{pick_number}.mp4"
        update_job(root, job_id, stage="rendering", message="Downloading only the selected source section")
        source_offset = _download_render_section(analysis["info"], candidate, source)
    staged = edits / f"clip-{pick_number}-{layout}.mp4"
    update_job(root, job_id, stage="rendering", message=f"Rendering {layout} vertical clip")
    framing = _render_with_opencv(source, staged, words, candidate, hook, source_offset=source_offset, layout=layout)
    update_job(root, job_id, stage="validating", message="Validating video and export package")
    validation = add_content_quality(
        probe_video(staged, minimum_duration=7.0, maximum_duration=30.0),
        inspect_media_quality(staged),
    )
    if not validation.get("valid"):
        raise MediaPipelineError("rendered clip failed validation: " + ", ".join(validation.get("errors", [])))
    destination = root / "output" / topic / output_date
    destination.mkdir(parents=True, exist_ok=True)
    video = destination / "clip-001.mp4"
    variation_video = destination / f"clip-{draft_kind}.mp4"
    info = analysis["info"]
    rights = info.get("rights", {"category": "legacy-confirmation", "confirmed_at": info["downloaded_at"]})
    third_party_draft = rights.get("category") == "third-party-review-draft"
    metadata = {
        "project_name": "TrendClip Studio",
        "topic_slug": topic,
        "suggested_title": hook.strip() or info["title"],
        "content_type": "third-party source review draft with original captions and reframing" if third_party_draft else "authorized source clip with original captions and reframing",
        "content_disclosure": "Source footage is third-party material. This local draft requires human review before publication." if third_party_draft else "Source footage was downloaded and transformed after the user confirmed reuse authorization.",
        "source_references": [{"title": info["title"], "url": info["source_url"], "publisher": info["channel"]}],
        "source_clip": {"job_id": job_id, "start": candidate["start"], "end": candidate["end"], "why": candidate["why"]},
        "draft": {"kind": draft_kind, "layout": layout, "candidate_n": int(pick_number), "framing": framing},
        "destinations": sorted(selected_destinations),
        "rights_confirmation": rights,
        "video_file": video.name,
        "generated_timestamp": datetime.now(timezone.utc).isoformat(),
        "validation_status": "passed",
        "validated_sha256": validation.get("sha256"),
    }
    from .cli import promote_export
    with tempfile.TemporaryDirectory(prefix=".trendclip-source-stage-", dir=destination) as temporary:
        promotion = Path(temporary)
        shutil.copy2(staged, promotion / "clip-001.mp4")
        _write_json(promotion / "clip-001.json", metadata)
        write_validation(validation, promotion / "validation.json")
        promote_export(promotion, destination)
    shutil.copy2(video, variation_video)
    _write_json(destination / f"clip-{draft_kind}.json", metadata)
    write_validation(validation, destination / f"validation-{draft_kind}.json")
    from .export_package import build_export_package
    manifest = build_export_package(root, destination, video=video, metadata=metadata, words=words, candidate=candidate, rights=info.get("rights", {}), destinations=selected_destinations)
    result = {"job_id": job_id, "video": str(video), "variation_video": str(variation_video), "draft_kind": draft_kind, "layout": layout, "metadata": metadata, "validation": validation, "manifest": manifest}
    _write_json(root / "state" / "media" / "latest-render.json", result)
    update_job(root, job_id, stage="complete", message="Validated export package is ready", output=str(destination))
    return result
