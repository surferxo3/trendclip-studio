"""Short-lived media worker that isolates native transcription and vision libraries."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .media_pipeline import MediaPipelineError, analyze_source, ingest_source, render_candidate_clip
from .codex_adapter import CodexAdapterError, invoke
from .drafts import editorial_summary


def _settings(root: Path):
    try:
        return json.loads((root / "config" / "settings.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"codex": {"enabled": False}}


def _optional_semantic_rerank(root: Path, result: dict) -> dict:
    config = _settings(root).get("codex", {})
    if not config.get("enabled", False):
        result["codex_assistance"] = {"used": False, "reason": "disabled"}
        return result
    payload = {"strategy": result.get("strategy"), "candidates": [{"id": str(item["n"]), "text": item.get("text", ""), "start": item["start"], "end": item["end"], "score_components": item.get("score_components", {}), "quality_components": item.get("quality_components", {}), "warnings": item.get("warnings", [])} for item in result.get("candidates", [])]}
    try:
        response = invoke(root, "semantic-highlight-rerank", payload, enabled=True, timeout=int(config.get("timeout_seconds", 120)), max_output_bytes=int(config.get("max_output_bytes", 262144)))
        candidate_ids = [item["id"] for item in payload["candidates"]]
        ranked_ids = response["ranked_candidate_ids"]
        if len(ranked_ids) != len(candidate_ids) or len(set(ranked_ids)) != len(ranked_ids) or set(ranked_ids) != set(candidate_ids):
            raise CodexAdapterError("Codex ranking did not contain each candidate exactly once")
        order = {value: index for index, value in enumerate(response["ranked_candidate_ids"])}
        result["candidates"] = sorted(result["candidates"], key=lambda item: order.get(str(item["n"]), len(order)))
        result.update(editorial_summary(result["candidates"], preferred_n=int(result["candidates"][0]["n"])))
        result["codex_assistance"] = {"used": True, "task": "semantic-highlight-rerank", "rationale": response["rationale"]}
    except CodexAdapterError as exc:
        result["codex_assistance"] = {"used": False, "reason": str(exc), "fallback": "deterministic-ranking"}
    path = root / "state" / "jobs" / str(result["job_id"]) / "analysis.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (root / "state" / "media" / "latest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(prog="trendclip-media-worker")
    parser.add_argument("--root", type=Path, required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze")
    analyze.add_argument("--url", required=True)
    analyze.add_argument("--max-minutes", type=int, default=90)
    analyze.add_argument("--use-browser-cookies", action="store_true")
    analyze.add_argument("--strategy", default="gaming", choices=("educational", "conversation", "gaming", "comedy", "craft"))
    analyze.add_argument("--rights-json", required=True)
    render = subparsers.add_parser("render")
    render.add_argument("--job-id", required=True)
    render.add_argument("--pick", type=int, required=True)
    render.add_argument("--topic", required=True)
    render.add_argument("--date", required=True)
    render.add_argument("--hook", default="")
    render.add_argument("--draft-kind", default="best-story")
    render.add_argument("--layout", default="balanced", choices=("balanced", "punch", "clean"))
    render.add_argument("--destinations", default="youtube,facebook,tiktok")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.command == "analyze":
        info = ingest_source(
            root,
            args.url,
            rights=json.loads(args.rights_json),
            max_minutes=args.max_minutes,
            use_browser_cookies=args.use_browser_cookies,
        )
        result = _optional_semantic_rerank(root, analyze_source(root, str(info["job_id"]), model_name="small", strategy=args.strategy))
    else:
        result = render_candidate_clip(root, args.job_id, args.pick, topic=args.topic, output_date=args.date, hook=args.hook, draft_kind=args.draft_kind, layout=args.layout, destinations=[item for item in args.destinations.split(",") if item])
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except MediaPipelineError as exc:
        print(json.dumps({"error": str(exc), "error_type": "media-pipeline"}, ensure_ascii=False))
        raise SystemExit(2)
