# Architecture

## Current scope

TrendClip Studio v0.5 implements configuration-driven discovery, selected-source YouTube ingestion, local transcription, strategy-based explainable moment ranking, vertical source clipping, complete export packages, original production, durable job state, and a loopback-only creator dashboard. Third-party inputs are recorded as local review drafts without claiming ownership or permission. Automatic publishing, scheduling, and platform analytics are intentionally outside the GTA 6 product scope.

## Data flow

```text
config/topics/<slug>.json
        │
        ▼
strict config loader ──► path boundary checks
        │
        ▼
FFmpeg filter-graph renderer ──► clip-001.mp4
        │                              │
        ├────────► metadata JSON       └──► ffprobe validator
        │                                      │
        └──────────────────────────────► validation.json
```

```text
approved feed config ──► bounded HTTPS fetch ──► XML parser
        │                                         │
        └──────────────────────────────► evidence-based ranking
                                                  │
                                                  ▼
                                      local dashboard / saved report
```

```text
selected YouTube URL + provenance record
        │
        ├──► anonymous access, or optional Chrome session (per job)
        ▼
yt-dlp audio + 240p proxy ──► Whisper + motion samples ──► explainable candidates
                                                        │
                                                        ▼
                               three automatic draft recipes + visual treatments
                                                        │
                                      selected range only downloaded by yt-dlp
                                                        ▼
isolated OpenCV renderer ──► FFmpeg encode/normalize ──► validation + complete package
```

## Responsibilities

- `trendclip.config`: parses and validates topic/video configuration; rejects malformed content early.
- `trendclip.paths`: confines generated files to a caller-selected output root inside the project.
- `trendclip.raster`: creates original PPM scene images with gradients, geometry, and an embedded block typeface using only Python byte buffers.
- `trendclip.render`: builds a topic-independent FFmpeg filter graph from those trusted local scenes.
- `trendclip.validate`: inspects the real file using ffprobe and evaluates platform-oriented technical checks.
- `trendclip.discovery`: fetches allowlisted HTTPS feeds, normalizes candidates, and ranks only with available evidence. Missing engagement/growth values stay null.
- `trendclip.candidate`: converts an explicitly selected saved candidate into a constrained original graphical briefing and source-cited metadata. It does not download or reuse the source media.
- `trendclip.media_pipeline`: records source provenance, downloads with yt-dlp, transcribes with Faster Whisper, ranks moments, renders vertical captions with OpenCV, encodes with FFmpeg, and validates the local review export.
- `trendclip.profiles`: validates the eleven configuration-driven niche profiles and discovery limits.
- `trendclip.rights`: records whether a job is a third-party review draft or an explicitly authorized source and validates platform scope.
- `trendclip.highlight_strategies`: applies format-specific signal weighting, speech-aware boundaries, editorial-quality components, and uncertainty warnings without requiring an LLM.
- `trendclip.drafts`: turns ranked evidence into unique Best story, High energy, and Quick hit draft recommendations and assigns balanced, punch, and clean treatments; the recommended draft requires no manual timestamp selection.
- `trendclip.benchmark`: validates two-reviewer benchmark manifests, calculates the documented weighted creator score, and prevents missing platforms or critical failures from being hidden by an aggregate.
- `trendclip.jobs`: persists atomic job stages and history.
- `trendclip.export_package`: creates captions, thumbnail, provenance, platform drafts, and checksummed manifests.
- `trendclip.codex_adapter`: optional disabled-by-default CLI assistance for semantic reranking and publishing drafts only.
- `trendclip.media_worker`: short-lived process boundary around native transcription/rendering libraries; emits structured results and safe errors.
- `trendclip.dashboard`: loopback-only HTTP UI/API for discovery, candidate selection, generation, preview, validation status, manual-upload tracking, and redacted JSONL diagnostics.
- `trendclip.cli`: validates a staged video, writes a coherent staged metadata set, and promotes all three artifacts with rollback protection; it returns non-zero on any failure.
- `config/topics`: content, factual citations, visual theme, timings, disclosure, and posting metadata.

## Extension points

New niches require a profile entry rather than a new pipeline. Source adapters return normalized candidate records and remain separate from highlight strategies and rendering. Publishing remains human-operated downstream of validated local exports.

## Deliberate constraints

- Local files only; no database, scheduler, or publishing API.
- Optional semantic assistance follows `docs/decisions/ADR-004-optional-semantic-analyzers.md`; it is not an agent runtime or pipeline dependency. Deterministic behavior remains available when disabled, unavailable, invalid, or rate limited.
- The first template requires 1080x1920 output.
- Typography intentionally uses a compact embedded uppercase block typeface.

