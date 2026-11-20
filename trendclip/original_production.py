"""Animated, original vertical explainer production using local composition tools."""

from __future__ import annotations

import json
import math
import re
import secrets
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

from .validate import add_content_quality, inspect_media_quality, probe_video, write_validation


class ProductionError(RuntimeError):
    pass


W, H, FPS = 1080, 1920, 30
NAVY = (21, 17, 12)
CYAN = (245, 220, 52)
CORAL = (89, 91, 255)
GREEN = (121, 229, 72)
WHITE = (246, 246, 242)
MUTED = (180, 177, 167)


def _log(root: Path, operation_id: str, event: str, message: str, level: str = "info") -> None:
    path = root / "state" / "logs" / "studio.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"timestamp": datetime.now(timezone.utc).isoformat(), "level": level, "event": event, "operation_id": operation_id, "message": message[:1000]}
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def _run(command: Sequence[str], *, timeout: int = 900) -> subprocess.CompletedProcess:
    completed = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    if completed.returncode:
        raise ProductionError((completed.stderr or completed.stdout or "production command failed")[-1800:].strip())
    return completed


def _write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _seconds(value: str) -> float:
    hours, minutes, seconds = value.replace(",", ".").split(":")
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def _timestamp(value: float, comma: bool = False) -> str:
    value = max(0.0, value)
    result = f"{int(value // 3600):02d}:{int(value % 3600 // 60):02d}:{value % 60:06.3f}"
    return result.replace(".", ",") if comma else result


def parse_vtt(path: Path) -> List[Dict[str, object]]:
    cues = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if " --> " not in line:
            continue
        left, right = line.split(" --> ", 1)
        text = lines[index + 1].strip() if index + 1 < len(lines) else ""
        text = re.sub(r"<[^>]+>", "", text)
        if text:
            cues.append({"start": _seconds(left), "end": _seconds(right.split()[0]), "text": text})
    return cues


def write_srt(cues: Sequence[Dict[str, object]], destination: Path) -> None:
    blocks = []
    for index, cue in enumerate(cues, 1):
        blocks.append(
            f"{index}\n{_timestamp(float(cue['start']), True)} --> {_timestamp(float(cue['end']), True)}\n{cue['text']}"
        )
    destination.write_text("\n\n".join(blocks) + "\n", encoding="utf-8")


def split_cues(cues: Sequence[Dict[str, object]], maximum_words: int = 7) -> List[Dict[str, object]]:
    """Split long sentence cues into readable, proportionally timed mobile captions."""
    result = []
    for cue in cues:
        words = str(cue["text"]).split()
        if len(words) <= maximum_words:
            result.append(dict(cue)); continue
        start, end = float(cue["start"]), float(cue["end"])
        chunks = [words[index:index + maximum_words] for index in range(0, len(words), maximum_words)]
        consumed = 0
        for chunk in chunks:
            chunk_start = start + (end - start) * consumed / len(words)
            consumed += len(chunk)
            chunk_end = start + (end - start) * consumed / len(words)
            result.append({"start": chunk_start, "end": chunk_end, "text": " ".join(chunk)})
    return result


def _text(frame, value: str, origin: Tuple[int, int], scale: float, color=WHITE, thickness: int = 3) -> None:
    import cv2
    cv2.putText(frame, value, origin, cv2.FONT_HERSHEY_DUPLEX, scale, (0, 0, 0), thickness + 7, cv2.LINE_AA)
    cv2.putText(frame, value, origin, cv2.FONT_HERSHEY_DUPLEX, scale, color, thickness, cv2.LINE_AA)


def _center(frame, value: str, y: int, scale: float, color=WHITE, thickness: int = 3) -> None:
    import cv2
    width = cv2.getTextSize(value, cv2.FONT_HERSHEY_DUPLEX, scale, thickness)[0][0]
    _text(frame, value, ((W - width) // 2, y), scale, color, thickness)


def _base(t: float):
    import cv2
    import numpy as np
    y = np.linspace(0, 1, H, dtype=np.float32)[:, None, None]
    top = np.array([28, 20, 15], dtype=np.float32)[None, None, :]
    bottom = np.array([8, 9, 13], dtype=np.float32)[None, None, :]
    frame = np.repeat((top * (1 - y) + bottom * y), W, axis=1).astype(np.uint8)
    for row in range(-200, H + 300, 180):
        offset = int(35 * math.sin(t * 0.7 + row * 0.01))
        cv2.line(frame, (0, row + offset), (W, row - 180 + offset), (45, 39, 32), 2, cv2.LINE_AA)
    for i in range(20):
        x = int((i * 137 + t * (18 + i % 4)) % (W + 100)) - 50
        yy = int((i * 241 + 100 * math.sin(t * 0.4 + i)) % H)
        cv2.circle(frame, (x, yy), 2 + i % 3, (80, 72, 55), -1, cv2.LINE_AA)
    return frame


def _round_rect(frame, p1, p2, color, radius=28, thickness=-1):
    import cv2
    x1, y1 = p1; x2, y2 = p2
    if thickness < 0:
        cv2.rectangle(frame, (x1 + radius, y1), (x2 - radius, y2), color, -1)
        cv2.rectangle(frame, (x1, y1 + radius), (x2, y2 - radius), color, -1)
        for x in (x1 + radius, x2 - radius):
            for y in (y1 + radius, y2 - radius):
                cv2.circle(frame, (x, y), radius, color, -1)
    else:
        cv2.rectangle(frame, p1, p2, color, thickness, cv2.LINE_AA)


def _ease(value: float) -> float:
    value = min(1.0, max(0.0, value))
    return value * value * (3 - 2 * value)


def _hero(frame, hero, p: float):
    import cv2
    scale = 1.03 + 0.07 * p
    hh, hw = hero.shape[:2]
    resized = cv2.resize(hero, (int(hw * scale), int(hh * scale)))
    target_h = H
    target_w = int(resized.shape[1] * target_h / resized.shape[0])
    resized = cv2.resize(resized, (target_w, target_h))
    x = max(0, (target_w - W) // 2 + int(40 * math.sin(p * math.pi)))
    frame[:] = cv2.addWeighted(frame, 0.28, resized[:, x:x + W], 0.72, 0)
    overlay = frame.copy(); cv2.rectangle(overlay, (0, 0), (W, H), (12, 8, 5), -1)
    frame[:] = cv2.addWeighted(frame, 0.72, overlay, 0.28, 0)


def _request(frame, p: float):
    import cv2
    x = int(-800 + 900 * _ease(p * 1.8))
    _round_rect(frame, (x, 610), (x + 820, 900), (42, 35, 27), 34)
    _text(frame, "FIND THE BEST LAPTOP", (x + 50, 710), 1.25)
    _text(frame, "UNDER $1,000", (x + 50, 815), 1.75, CYAN, 4)
    r = int(140 + 14 * math.sin(p * 12))
    cv2.circle(frame, (540, 1160), r, (61, 47, 29), -1, cv2.LINE_AA)
    cv2.circle(frame, (540, 1160), r, CYAN, 5, cv2.LINE_AA)
    _center(frame, "AI", 1190, 2.1, CYAN, 5)


def _compare(frame, p: float):
    import cv2
    for i, (name, score, color) in enumerate((("OPTION A", 92, CYAN), ("OPTION B", 84, GREEN), ("OPTION C", 76, CORAL))):
        x = int(110 + i * 310 + (1 - _ease(p * 2 - i * .2)) * 600)
        _round_rect(frame, (x, 610), (x + 260, 1180), (41, 35, 28), 24)
        cv2.rectangle(frame, (x + 28, 665), (x + 232, 840), (75 + i * 12, 70, 62), -1)
        cv2.circle(frame, (x + 130, 750), 55, color, 4, cv2.LINE_AA)
        _text(frame, name, (x + 26, 930), .72, WHITE, 2)
        _text(frame, f"{score}%", (x + 55, 1045), 1.35, color, 3)
        cv2.rectangle(frame, (x + 30, 1100), (x + 30 + int(200 * score / 100), 1120), color, -1)


def _checkout(frame, p: float):
    import cv2
    cv2.line(frame, (130, 1000), (950, 1000), (70, 64, 53), 10, cv2.LINE_AA)
    x = int(160 + min(1, p * 1.6) * 440)
    cv2.circle(frame, (x, 1000), 74, CYAN, -1, cv2.LINE_AA)
    _center(frame, "PAY", 1023, 0.75, NAVY, 2) if x == 540 else None
    cv2.rectangle(frame, (650, 790), (690, 1210), CORAL, -1)
    for offset in range(-160, 220, 70):
        cv2.line(frame, (650, 900 + offset), (690, 860 + offset), WHITE, 8, cv2.LINE_AA)
    _text(frame, "APPROVAL GATE", (545, 1320), 1.05, CORAL, 3)


def _controls(frame, p: float):
    import cv2
    rows = (("PRODUCT", "LAPTOP"), ("BUDGET", "$1,000 MAX"), ("QUANTITY", "ONE"), ("EXPIRES", "TODAY"))
    for i, (key, value) in enumerate(rows):
        y = 560 + i * 220
        alpha = _ease(p * 2.2 - i * .18)
        x = int(80 + (1 - alpha) * 600)
        _round_rect(frame, (x, y), (1000, y + 160), (40, 34, 27), 22)
        _text(frame, key, (x + 35, y + 65), .78, MUTED, 2)
        _text(frame, value, (x + 35, y + 125), 1.08, CYAN if i < 2 else GREEN, 3)
        cv2.circle(frame, (930, y + 80), 25, GREEN, -1, cv2.LINE_AA)
        _text(frame, "✓", (914, y + 92), .65, NAVY, 2)


def _flow(frame, p: float):
    import cv2
    nodes = (("YOU", 130), ("AGENT", 335), ("TOKEN", 540), ("NETWORK", 745), ("ISSUER", 950))
    for i, (label, y) in enumerate(nodes):
        color = GREEN if i in (0, 4) else CYAN
        cv2.circle(frame, (540, y + 500), 68, (41, 35, 28), -1, cv2.LINE_AA)
        cv2.circle(frame, (540, y + 500), 68, color, 4, cv2.LINE_AA)
        _center(frame, label, y + 520, .75 if len(label) < 7 else .58, color, 2)
        if i < len(nodes) - 1:
            cv2.line(frame, (540, y + 568), (540, nodes[i + 1][1] + 432), (72, 64, 48), 8, cv2.LINE_AA)
    travel = int(630 + ((p * 4) % 1) * 800)
    cv2.circle(frame, (540, travel), 18, WHITE, -1, cv2.LINE_AA)


def _future(frame, p: float):
    import cv2
    horizon = 1150
    for i in range(12):
        x = 60 + i * 90
        top = int(horizon - (120 + 150 * math.sin(i * .8 + p * 3)))
        cv2.rectangle(frame, (x, top), (x + 48, horizon), (37, 33, 28), -1)
        cv2.line(frame, (x + 24, top), (540, 650), CYAN if i % 3 == 0 else (62, 57, 46), 2, cv2.LINE_AA)
    cv2.circle(frame, (540, 650), int(80 + 12 * math.sin(p * 10)), CYAN, 5, cv2.LINE_AA)
    _center(frame, "NOT EVERY ASSISTANT", 1370, 1.15, WHITE, 3)
    _center(frame, "CAN DO THIS", 1470, 1.35, CORAL, 4)


def _question(frame, p: float):
    import cv2
    pulse = int(5 + 4 * math.sin(p * 10))
    _round_rect(frame, (70, 650), (1010, 950), (34, 48, 37), 28)
    _round_rect(frame, (70, 1010), (1010, 1310), (48, 35, 35), 28)
    cv2.rectangle(frame, (70, 650), (1010, 950), GREEN, pulse, cv2.LINE_AA)
    cv2.rectangle(frame, (70, 1010), (1010, 1310), CORAL, pulse, cv2.LINE_AA)
    _center(frame, "ONE-TIME BUDGET", 825, 1.35, GREEN, 4)
    _center(frame, "NO AI CHECKOUT", 1185, 1.35, CORAL, 4)


VISUALS = {"request": _request, "compare": _compare, "checkout": _checkout, "controls": _controls, "flow": _flow, "future": _future, "question": _question}


def _caption(frame, cues, t: float):
    import cv2
    active = next((cue for cue in cues if float(cue["start"]) <= t <= float(cue["end"])), None)
    if not active:
        return
    words = str(active["text"]).upper().split()
    lines, current = [], ""
    for word in words:
        proposed = f"{current} {word}".strip()
        if len(proposed) > 28 and current:
            lines.append(current); current = word
        else:
            current = proposed
    if current: lines.append(current)
    lines = lines[-2:]
    top = 1570 - 70 * (len(lines) - 1)
    overlay = frame.copy()
    _round_rect(overlay, (48, top - 70), (1032, 1735), (11, 10, 9), 24)
    frame[:] = cv2.addWeighted(frame, .25, overlay, .75, 0)
    for i, line in enumerate(lines):
        _center(frame, line, top + i * 82, 1.25, WHITE, 3)


def _scene_title(frame, scene, p: float):
    if p > .78:
        return
    _text(frame, scene["eyebrow"], (72, 155), .76, CYAN, 2)
    for index, line in enumerate(scene["headline"].split("\n")):
        _text(frame, line, (70, 275 + index * 105), 1.48, WHITE, 4)


def _render_video(config, hero, cues, narration: Path, output: Path, total: float, preview_dir: Path):
    import cv2
    boundaries = [0.0]
    for scene in config["scenes"]:
        boundaries.append(boundaries[-1] + total * float(scene["weight"]))
    boundaries[-1] = total
    command = [
        "ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "pipe:0",
        "-i", str(narration), "-f", "lavfi", "-i", f"sine=frequency=72:sample_rate=48000:duration={total}",
        "-filter_complex", "[1:a]loudnorm=I=-16:TP=-1.5:LRA=11[voice];[2:a]volume=0.025,afade=t=in:d=1.5,afade=t=out:st=" + f"{max(0,total-2):.3f}" + ":d=2[bed];[voice][bed]amix=inputs=2:duration=longest:weights='1 0.35',loudnorm=I=-16:TP=-1.5:LRA=11[a]",
        "-map", "0:v", "-map", "[a]", "-c:v", "libx264", "-preset", "medium", "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-ar", "48000", "-ac", "2", "-movflags", "+faststart", "-shortest", str(output),
    ]
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    previews = []
    for frame_index in range(int(math.ceil(total * FPS))):
        t = frame_index / FPS
        scene_index = min(len(config["scenes"]) - 1, next((i for i in range(len(config["scenes"])) if boundaries[i] <= t < boundaries[i + 1]), len(config["scenes"]) - 1))
        scene = config["scenes"][scene_index]
        duration = boundaries[scene_index + 1] - boundaries[scene_index]
        p = (t - boundaries[scene_index]) / max(.001, duration)
        frame = _base(t)
        if scene["visual"] == "hero": _hero(frame, hero, p)
        else: VISUALS[scene["visual"]](frame, p)
        _scene_title(frame, scene, p)
        _caption(frame, cues, t)
        if abs(p - .52) < 1 / FPS and len(previews) <= scene_index:
            path = preview_dir / f"scene-{scene_index + 1:02d}.jpg"; cv2.imwrite(str(path), frame); previews.append(path)
        assert process.stdin is not None
        process.stdin.write(frame.tobytes())
    assert process.stdin is not None
    process.stdin.close()
    stderr = process.stderr.read().decode("utf-8", "replace") if process.stderr else ""
    if process.wait() != 0:
        raise ProductionError(stderr[-1800:] or "video encoder failed")
    return boundaries, previews


def _contact_sheet(previews: Sequence[Path], destination: Path) -> None:
    import cv2
    images = [cv2.resize(cv2.imread(str(path)), (270, 480)) for path in previews]
    rows = [cv2.hconcat(images[i:i + 4]) for i in range(0, 8, 4)]
    cv2.imwrite(str(destination), cv2.vconcat(rows))


def produce(production_dir: Path) -> Dict[str, object]:
    import cv2
    started = time.perf_counter()
    root = Path(__file__).resolve().parent.parent
    operation_id = secrets.token_hex(6)
    _log(root, operation_id, "original-production-start", production_dir.name)
    config = json.loads((production_dir / "production.json").read_text(encoding="utf-8"))
    output = production_dir / "output"; output.mkdir(parents=True, exist_ok=True)
    preview_dir = output / "scene-previews"; preview_dir.mkdir(exist_ok=True)
    narration = output / "narration.mp3"; vtt = output / "captions.vtt"
    if not narration.is_file() or narration.stat().st_size == 0 or not vtt.is_file() or vtt.stat().st_size == 0:
        _run([sys.executable, "-m", "edge_tts", "--file", str(production_dir / "script.txt"), "--voice", config["voice"], f"--rate={config['voice_rate']}", "--write-media", str(narration), "--write-subtitles", str(vtt), "--no-progress"], timeout=240)
    cues = split_cues(parse_vtt(vtt))
    if not cues:
        raise ProductionError("narration did not return subtitle timings")
    write_srt(cues, output / "captions.srt")
    audio_info = json.loads(_run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(narration)]).stdout)
    total = float(audio_info["format"]["duration"]) + .6
    if not 50 <= total <= 60:
        raise ProductionError(f"narration duration {total:.2f}s is outside the 50–60 second target")
    hero = cv2.imread(str(production_dir / "assets" / "agentic-commerce-hero.png"))
    if hero is None:
        raise ProductionError("hero illustration is missing")
    video = output / "final-video.mp4"
    boundaries, previews = _render_video(config, hero, cues, narration, video, total, preview_dir)
    validation = add_content_quality(
        probe_video(video, minimum_duration=50, maximum_duration=60),
        inspect_media_quality(video),
    )
    write_validation(validation, output / "validation.json")
    if not validation["valid"]:
        raise ProductionError("final video failed validation: " + ", ".join(validation["errors"]))
    thumbnail = _base(0); _hero(thumbnail, hero, .35)
    _text(thumbnail, "CAN AI SPEND", (62, 180), 1.75, WHITE, 5); _text(thumbnail, "YOUR MONEY?", (62, 315), 1.95, CYAN, 5)
    _round_rect(thumbnail, (60, 1430), (1020, 1585), (21, 16, 12), 24); _center(thumbnail, "THE CHECKOUT QUESTION", 1530, 1.02, CORAL, 3)
    cv2.imwrite(str(output / "thumbnail.png"), thumbnail)
    _contact_sheet(previews, output / "storyboard-contact-sheet.jpg")
    storyboard = {"title": config["title"], "duration_seconds": round(total, 3), "scenes": []}
    for i, scene in enumerate(config["scenes"]):
        storyboard["scenes"].append({**scene, "number": i + 1, "start": round(boundaries[i], 3), "end": round(boundaries[i + 1], 3), "preview": f"scene-previews/scene-{i + 1:02d}.jpg"})
    _write_json(output / "storyboard.json", storyboard)
    _write_json(output / "publishing-metadata.json", config["publishing"])
    shutil.copyfile(production_dir / "script.txt", output / "final-script.txt")
    shutil.copyfile(production_dir / "research-references.md", output / "research-references.md")
    shutil.copyfile(production_dir / "asset-manifest.json", output / "asset-manifest.json")
    elapsed = time.perf_counter() - started
    report = {
        "production_id": config["id"], "generated_at": datetime.now(timezone.utc).isoformat(),
        "generation_seconds": round(elapsed, 3), "generation_minutes": round(elapsed / 60, 2),
        "initial_cold_generation_seconds": config.get("initial_cold_generation_seconds"),
        "paid_provider_cost_usd": 0.0, "cost_note": "No paid provider API was used. Edge TTS and local compute were unmetered; the original illustration used the built-in image-generation tool.",
        "voice": config["voice"], "validation": validation,
        "artifacts": ["final-video.mp4", "thumbnail.png", "captions.srt", "final-script.txt", "research-references.md", "asset-manifest.json", "storyboard-contact-sheet.jpg", "storyboard.json", "publishing-metadata.json", "validation.json"],
    }
    _write_json(output / "production-report.json", report)
    _log(root, operation_id, "original-production-complete", f"duration={total:.3f}s generation={elapsed:.3f}s")
    return report


def main(argv=None) -> int:
    target = Path(argv[0] if argv else "productions/experiment-001-agentic-commerce").resolve()
    try:
        print(json.dumps(produce(target), indent=2))
        return 0
    except ProductionError as exc:
        root = Path(__file__).resolve().parent.parent
        _log(root, "unassigned", "original-production-error", str(exc), "error")
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
