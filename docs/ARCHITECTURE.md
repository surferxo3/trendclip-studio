# Architecture

## Current scope

TrendClip Studio v0.5 implements configuration-driven discovery, selected-source YouTube ingestion, local transcription, strategy-based explainable moment ranking, vertical source clipping, complete export packages, original production, durable job state, and a loopback-only creator dashboard. Third-party inputs are recorded as local review drafts without claiming ownership or permission. Automatic publishing, scheduling, and platform analytics are intentionally outside the GTA 6 product scope.

TrendClip has two production paths:

1. **Source clipping** discovers current YouTube videos, analyzes a selected source, recommends three editorial drafts, and renders review-ready vertical variations.
2. **Original production** turns a reviewed script and scene configuration into an original narrated motion-graphics explainer without third-party footage.

Both paths converge on local FFmpeg encoding, ffprobe validation, a local review package, and manual publishing.

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

```text
reviewed research + script + scene configuration
        │
        ├──► Edge TTS narration + timing cues
        ├──► OpenCV motion graphics + original assets
        └──► mobile-readable captions
                         │
                         ▼
             FFmpeg audio mix + encode
                         │
                         ▼
       validation + thumbnail + contact sheet + metadata
```

## Runtime modes

| Mode | Entry point | Purpose |
|---|---|---|
| Studio UI | `python -m trendclip studio` or platform launcher | Starts the loopback server, refreshes discovery, opens the browser, and provides the complete interactive workflow. |
| Server only | `python -m trendclip dashboard` | Starts the same local UI/API without opening a browser. |
| Command line | `doctor`, `discover`, `render`, `produce-original`, `benchmark` | Diagnostics, scripting, deterministic original rendering, and developer workflows. |

The complete selected-source remix workflow is currently UI-led. Version 0.5 does not expose one stable headless command for every source-selection, analysis, draft-review, and variation step.

## Responsibilities

- `trendclip.config`: parses and validates topic/video configuration; rejects malformed content early.
- `trendclip.paths`: confines generated files to a caller-selected output root inside the project.
- `trendclip.raster`: creates original PPM scene images with gradients, geometry, and an embedded block typeface using only Python byte buffers.
- `trendclip.render`: builds a topic-independent FFmpeg filter graph from those trusted local scenes.
- `trendclip.validate`: inspects the real file using ffprobe and evaluates platform-oriented technical checks.
- `trendclip.discovery`: fetches allowlisted HTTPS feeds, normalizes candidates, and ranks only with available evidence. Missing engagement/growth values stay null.
- `trendclip.candidate`: converts an explicitly selected saved candidate into a constrained original graphical briefing and source-cited metadata. It does not download or reuse the source media.
- `trendclip.media_pipeline`: records source provenance, downloads with yt-dlp, transcribes with Faster Whisper, ranks moments, detects embedded portrait framing, renders adaptive vertical compositions and captions with OpenCV, encodes with FFmpeg, and validates the local review export.
- `trendclip.profiles`: validates the eleven configuration-driven niche profiles and discovery limits.
- `trendclip.rights`: records whether a job is a third-party review draft or an explicitly authorized source and validates platform scope.
- `trendclip.highlight_strategies`: applies format-specific signal weighting, speech-aware boundaries, editorial-quality components, and uncertainty warnings without requiring an LLM.
- `trendclip.drafts`: turns ranked evidence into conservative Top pick, High energy, and Quick hit draft recommendations and assigns balanced, punch, and clean treatments; the recommended draft requires no manual timestamp selection.
- `trendclip.benchmark`: validates two-reviewer benchmark manifests, calculates the documented weighted creator score, and prevents missing platforms or critical failures from being hidden by an aggregate.
- `trendclip.jobs`: persists atomic job stages and history.
- `trendclip.export_package`: creates captions, thumbnail, provenance, platform drafts, and checksummed manifests.
- `trendclip.codex_adapter`: optional disabled-by-default CLI assistance for semantic reranking and publishing drafts only.
- `trendclip.media_worker`: short-lived process boundary around native transcription/rendering libraries; emits structured results and safe errors.
- `trendclip.dashboard`: loopback-only HTTP UI/API for discovery, candidate selection, generation, preview, validation status, manual-upload tracking, and redacted JSONL diagnostics.
- `trendclip.cli`: validates a staged video, writes a coherent staged metadata set, and promotes all three artifacts with rollback protection; it returns non-zero on any failure.
- `config/topics`: content, factual citations, visual theme, timings, disclosure, and posting metadata.

## Local storage and diagnostics

```text
trendclip-studio/
├── config/                  # Profiles, settings, sources, and topics
├── dashboard/               # Browser UI
├── productions/             # Reviewed original-production projects
├── output/                  # Validated generated packages; ignored by Git
├── state/
│   ├── discovery/           # Latest discovery reports
│   ├── jobs/                # Durable download/transcription/render state
│   ├── cache/codex/         # Optional structured-task cache
│   ├── logs/studio.log      # Redacted JSONL operational log
│   └── media/               # Latest analysis state
├── tests/
└── trendclip/
```

Media jobs use atomic JSON records with a bounded stage history. Native transcription and rendering run in short-lived worker processes so a native-library failure does not terminate the dashboard. Workers are an availability boundary, not a security sandbox. Logs carry operation/job identifiers and never intentionally record browser cookie values.

## Original-production contract

Each project under `productions/<production-id>/` contains a reviewed configuration, script, research references, asset manifest, and local assets. `trendclip.original_production` creates narration, captions, continuous programmatic animation, a thumbnail, contact sheet, publishing metadata, production report, and technical validation. This is a 2D/2.5D template system rather than a general text-to-video model. Edge TTS requires network access; completed narration is cached locally.

## Model and media responsibilities

| Capability | Implementation |
|---|---|
| Speech transcription | Faster Whisper, local CPU/INT8 by default |
| Moment scoring | Deterministic profile-specific audio, speech, replay, motion, and shot-change rules |
| Optional semantic reranking/copy | Bounded Codex CLI adapter, disabled by default, schema validated, deterministic fallback |
| Source composition | OpenCV geometry, persistent portrait-region detection, shot-aware adaptive framing with hysteresis, captions, and visual treatments |
| Original narration | Edge TTS |
| Encoding and audio normalization | FFmpeg |
| Structural and content checks | ffprobe plus black/freeze/silence inspection |

No local general-purpose LLM is required. Framing detection uses repeated column-activity evidence, one stable portrait crop, and short hysteresis at shot changes. It records the framing mode, confidence, crop, sample count, application policy, and applied-frame ratio in export metadata. It deliberately falls back when evidence is weak and does not claim face, speaker, object, HUD, or action tracking.

## Creator-experience contract

- The normal path emphasizes video choices, preview, and draft comparison rather than formulas or system stages.
- Top pick, High energy, and Quick hit show reasons, confidence, and warnings; raw signals stay secondary.
- Download, transcription, analysis, rendering, and validation provide progressive status.
- Completed work is preserved when a later stage fails, and errors provide a plain-language recovery action.
- Scores are evidence, not “viral probability.” TrendClip never guarantees reach, rights clearance, monetization, or platform acceptance.
- The interface uses a restrained dark canvas, readable type, one primary action color, accessible focus/contrast, reduced-motion support, and mobile-sized interaction targets.

## Extension points

New niches require a profile entry rather than a new pipeline. Source adapters return normalized candidate records and remain separate from highlight strategies and rendering. Publishing remains human-operated downstream of validated local exports.

## Deliberate constraints

- Local files only; no database, scheduler, or publishing API.
- Optional semantic assistance follows `docs/decisions/ADR-004-optional-semantic-analyzers.md`; it is not an agent runtime or pipeline dependency. Deterministic behavior remains available when disabled, unavailable, invalid, or rate limited.
- The first template requires 1080x1920 output.
- Typography intentionally uses a compact embedded uppercase block typeface.

