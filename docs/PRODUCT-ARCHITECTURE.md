# TrendClip Studio — Product Architecture

**Version:** 0.5.0  
**Updated:** 2026-11-20  
**Deployment model:** Local macOS application, browser-based control dashboard, manual publishing

## 1. Product purpose

TrendClip Studio is a local video-production system with two supported workflows:

1. **Authorized source clipping** — discover recent YouTube videos, download a user-approved source, identify strong moments, and transform a selected moment into a captioned vertical clip.
2. **Original animated production** — turn a reviewed script and scene plan into an original narrated motion-graphics explainer without using third-party footage.

Both workflows produce validated local MP4 files for human review and manual upload. YouTube, Facebook, and TikTok publishing APIs are not connected.

## 2. System context

```text
                         ┌──────────────────────────┐
                         │      Local browser       │
                         │  TrendClip Studio UI     │
                         └────────────┬─────────────┘
                                      │ HTTP on 127.0.0.1
                         ┌────────────▼─────────────┐
                         │   Local dashboard/API    │
                         │ discovery · jobs · logs  │
                         └──────┬──────────┬────────┘
                                │          │
              ┌─────────────────▼──┐    ┌──▼────────────────────┐
              │ Source clip path   │    │ Original production   │
              │ YouTube → moments  │    │ Script → animation    │
              └──────────┬─────────┘    └──────────┬────────────┘
                         │                         │
                         └────────────┬────────────┘
                                      ▼
                         ┌──────────────────────────┐
                         │ FFmpeg encode + ffprobe  │
                         │ technical validation     │
                         └────────────┬─────────────┘
                                      ▼
                         ┌──────────────────────────┐
                         │ Local review package     │
                         │ MP4 · captions · JSON    │
                         │ thumbnail · storyboard   │
                         └──────────────────────────┘
```

## 3. Major components

| Component | Responsibility |
|---|---|
| `dashboard/` | Browser interface for story discovery, source selection, reuse confirmation, moment selection, video review, download, and manual-upload tracking. |
| `trendclip.dashboard` | Loopback-only HTTP server and JSON API. Starts discovery jobs, isolated media workers, serves exports with byte-range support, and writes structured logs. |
| `trendclip.discovery` | Searches recent YouTube uploads, retrieves metadata through yt-dlp, filters by topic, ranks by observed views per hour, and merges approved official-feed fallbacks. |
| `trendclip.profiles` | Loads and strictly validates configuration-driven niches, filters, and strategies. |
| `trendclip.rights` | Enforces reusable-source categories, permission evidence, scope, and platform choices. |
| `trendclip.highlight_strategies` | Scores educational, conversation, gaming, comedy, and craft moments using explainable local signals. |
| `trendclip.jobs` | Persists atomic job stage, status, message, and bounded history records. |
| `trendclip.export_package` | Builds SRT, thumbnail, provenance, platform drafts, and checksummed manifest around each validated clip. |
| `trendclip.codex_adapter` | Provides optional bounded semantic reranking and publishing-copy drafts through an authenticated Codex CLI session; disabled by default. |
| `trendclip.media_pipeline` | Downloads approved sources, extracts audio, transcribes speech, calculates moment scores, reframes selected frames, draws captions/hooks, encodes, and validates source clips. |
| `trendclip.media_worker` | Runs transcription and source rendering in short-lived processes to isolate native media libraries and return structured results/errors. |
| `trendclip.original_production` | Produces original animated explainers from reviewed scripts and scene configurations, including narration, subtitles, motion graphics, thumbnails, contact sheets, metadata, and reports. |
| `trendclip.render` | Original static-graphic renderer retained as a deterministic fallback/template renderer. |
| `trendclip.raster` | Dependency-light raster scene creation using programmatic geometry and an embedded block typeface. |
| `trendclip.validate` | Uses ffprobe to verify resolution, codecs, frame rate, pixel format, duration, container, and SHA-256 digest. |
| `trendclip.config` | Loads and validates topic configuration, dimensions, timings, colors, sources, disclosures, and metadata. |
| `trendclip.paths` | Enforces output-path containment inside approved project locations. |
| `trendclip.cli` | Provides render, discovery, dashboard, Studio, and original-production commands. |

## 4. Workflow A — Authorized source clipping

### 4.1 Discovery

```text
Topic configuration
      │
      ├──► Recent YouTube search via yt-dlp
      │        │
      │        ├── title/keyword filtering
      │        ├── upload-age filtering
      │        └── views-per-hour ranking
      │
      └──► Approved official Atom/RSS feeds
               │
               └── relevance + freshness + reliability ranking
                            │
                            ▼
                   Combined discovery report
```

Recent YouTube candidates are ranked primarily by:

```text
views_per_hour = observed_view_count / hours_since_publication
```

The value is logarithmically normalized for the UI. It is a point-in-time discovery signal, not proof of platform-wide trend status.

### 4.2 Source provenance and ingestion

The user selects a discovered candidate. Normal discovery records it as a `third-party-review-draft` without asking the user to claim ownership. Explicitly owned, licensed, or campaign-provided sources may carry stronger authorization records.

yt-dlp then:

- validates that the URL is an allowed HTTPS YouTube host;
- disables playlist ingestion;
- retrieves source metadata;
- downloads a bounded source file;
- optionally uses the locally logged-in Chrome YouTube session;
- uses the installed Node runtime for YouTube JavaScript challenge solving;
- records provenance without storing or logging browser cookie values.

Downloaded sources are cached under a deterministic job identifier:

```text
state/jobs/<job-id>/
├── info.json
├── source.mp4
├── audio.wav
├── transcript.json
├── analysis.json
├── rights.json
├── job.json
└── edits/
```

### 4.3 Transcription and signal extraction

FFmpeg extracts mono 16 kHz audio. Faster-Whisper runs locally with the `small` model, CPU execution, and INT8 computation.

The transcript contains word-level timestamps:

```json
{"w": "example", "s": 12.4, "e": 12.92}
```

NumPy calculates one-second RMS audio levels in decibels. The pipeline also derives speech density and recognizes a bounded list of hype-language patterns. YouTube most-replayed heatmap data is used when available.

### 4.4 Moment scoring

Moment selection remains deterministic by default; no local general-purpose LLM is required. Each profile selects a reusable strategy and every candidate records its score components.

```text
strategy score = weighted(
  loudness, speech density, emphasis language,
  punchline/setup language, viewer replay, visual change
)
```

Weights differ for educational, conversation, gaming, comedy, and craft profiles. The scorer:

1. identifies the highest timeline peaks;
2. builds 7–30 second windows around those peaks;
3. aligns boundaries with nearby transcript words;
4. removes overlapping selections;
5. records component-level explanations and returns up to eight ranked candidates;
6. falls back to the opening segment when no meaningful peak exists.

### 4.5 Source-clip composition

OpenCV reads every frame in the selected time range and performs the visual composition:

- 9:16 vertical canvas;
- blurred full-frame background;
- resized original foreground;
- timed opening hook;
- active-word captions;
- profanity masking.

FFmpeg receives the raw composed frames, selects the matching source audio, normalizes audio, encodes H.264/AAC, and packages the MP4.

The current crop is deterministic. It does not yet use face tracking, object tracking, scene understanding, or a multimodal vision model.

## 5. Workflow B — Original animated production

```text
Reviewed research
      ▼
Original script + scene configuration
      ├──► Edge TTS narration + timing cues
      ├──► VTT → mobile-readable SRT captions
      ├──► Original generated illustration assets
      └──► OpenCV continuous motion graphics
                         │
                         ▼
               FFmpeg audio mix + encode
                         │
                         ▼
                    ffprobe validation
```

### 5.1 Inputs

Each production lives under:

```text
productions/<production-id>/
├── production.json
├── script.txt
├── research-references.md
├── asset-manifest.json
├── assets/
└── output/
```

The production configuration defines:

- title and production identifier;
- narration voice and rate;
- scene names, timing weights, headings, and visual templates;
- YouTube, Facebook, and TikTok publishing metadata.

### 5.2 Narration and subtitles

The installed Edge TTS integration generates narration and timing cues. Long cues are split into shorter, proportionally timed captions for mobile readability. The external `captions.srt` file and burned video captions use the same cue source.

No paid TTS provider is required by the current implementation. TTS requires network access; generated narration is cached locally for repeat renders.

### 5.3 Motion graphics

OpenCV generates continuous 1080x1920 frames at 30 fps. Scene-specific animation includes:

- moving backgrounds and particles;
- eased entrances and exits;
- animated product cards and comparison bars;
- approval boundaries and payment-token movement;
- user-control panels;
- animated payment-flow diagrams;
- synchronized narration captions;
- selective generated 3D/editorial artwork with camera movement.

This is a programmatic 2D/2.5D animation system. It is not a general text-to-video diffusion model.

### 5.4 Export package

The original-production path creates:

```text
output/
├── final-video.mp4
├── thumbnail.png
├── captions.srt
├── final-script.txt
├── research-references.md
├── asset-manifest.json
├── storyboard-contact-sheet.jpg
├── storyboard.json
├── publishing-metadata.json
├── production-report.json
└── validation.json
```

## 6. Shared media and validation layer

Both workflows converge on FFmpeg and ffprobe.

### FFmpeg responsibilities

- audio extraction;
- source-audio selection;
- narration/music-bed mixing;
- loudness normalization;
- H.264 encoding;
- AAC encoding;
- pixel-format conversion to `yuv420p`;
- MP4 fast-start packaging.

### Validation responsibilities

The validator checks the real output file for:

- 1080x1920 dimensions;
- H.264 video;
- AAC audio;
- `yuv420p` pixel format;
- expected frame rate;
- expected duration range;
- MP4 container;
- successful ffprobe parsing;
- SHA-256 digest.

Validation does not establish copyright permission, factual accuracy, platform acceptance, or audience suitability.

## 7. Dashboard and API architecture

The dashboard server binds only to:

```text
127.0.0.1
localhost
```

It does not expose a public network service.

State-changing requests:

- require a custom local-action header;
- reject non-loopback browser origins;
- validate profile, date, source URL, rights record, settings, and identifiers;
- return concise user-facing errors;
- record structured diagnostic events.

The current UI directly exposes the source-clipping workflow. Original animated production is currently available through the CLI:

```bash
python3 -m trendclip produce-original
```

Adding original-production controls to the dashboard is a future UI enhancement, not a new backend architecture requirement.

## 8. Local storage architecture

```text
trendclip-studio/
├── config/                  # Profiles, settings, and original-production topics
├── dashboard/               # Browser UI
├── docs/                    # Architecture, security, decisions, operations
├── output/                  # Validated source-clipping exports
├── productions/             # Original production projects and packages
├── state/
│   ├── discovery/           # Latest discovery reports
│   ├── jobs/                # Download/transcription/analysis jobs
│   ├── cache/codex/         # Structured optional-task cache
│   ├── codex-tmp/           # Short-lived isolated task directories
│   ├── logs/studio.log      # Structured JSONL operational log
│   ├── media/               # Latest media analysis state
│   └── tracking.json        # Manual-upload records
├── tests/                   # Unit and regression tests
└── trendclip/               # Python application modules
```

Generated media and state are local and excluded from version control where appropriate.

## 9. Logging and error handling

Operational events are written as newline-delimited JSON to:

```text
state/logs/studio.log
```

Logged events include:

- Studio startup;
- discovery start/completion;
- media-worker start/completion/failure;
- browser-session usage without cookie values;
- original-production start/completion/failure;
- request-level errors.

Worker runs receive an `operation_id` in logs. Each media job also has durable `job.json` stage, status, message, timestamps, and bounded history.

Native transcription and source rendering run in separate worker processes. This prevents conflicting native libraries from destabilizing the dashboard process, but it is not a security sandbox.

## 10. Security and rights boundaries

- Final publishing is manual.
- No platform OAuth credentials are stored.
- No upload or scheduling endpoints exist.
- Every downloaded source receives a provenance category; discovered sources default to third-party review drafts.
- A logged-in browser session improves access but does not establish ownership or publication rights.
- Browser cookie values are not copied into TrendClip state or logs.
- Downloaded media is treated as untrusted input.
- Remote source hosts and URL schemes are restricted.
- Paths are resolved and confined to approved project locations.
- Subprocesses receive argument arrays without shell interpolation.
- Original productions record asset provenance and research references.
- Technical validation is separate from editorial, rights, and legal review.

## 11. Model usage

| Capability | Model/system used |
|---|---|
| Speech transcription | Faster-Whisper `small`, CPU INT8 |
| Optional semantic reranking | Codex CLI using ChatGPT authentication, disabled by default, schema bounded, deterministic fallback |
| Optional publishing drafts | Codex CLI under the same bounded adapter; deterministic drafts remain available |
| Moment scoring | Strategy-specific deterministic NumPy rules |
| Visual frame selection | Deterministic timeline selection; no vision model |
| Source reframing | OpenCV geometry |
| Original narration | Edge TTS |
| Original illustration | Optional generated image asset, recorded in the asset manifest |
| Video encoding | FFmpeg |

No local general-purpose LLM is required. Faster-Whisper is a local speech-recognition model. Optional Codex use is remote, explicit, and restricted to two non-essential structured tasks.

## 12. Current deployment sequence

```text
Start TrendClip Studio.command
        │
        ├── verify project-local .venv
        ├── reuse an existing server when available
        └── python -m trendclip studio
                  │
                  ├── bind 127.0.0.1:8765
                  ├── open browser
                  └── refresh discovery in background
```

The server remains a foreground local process and stops when its terminal process ends.

## 13. Current limitations

- Discovery is YouTube-only.
- No live-stream recording or chat-spike analysis.
- No face, speaker, object, or action tracking.
- No multimodal scene-quality model.
- No local general-purpose LLM; optional Codex assistance consumes plan allowance when enabled.
- Original animation templates are production-specific rather than a general visual editor.
- Edge TTS requires network access.
- The dashboard does not yet expose original-production configuration.
- No automatic publishing, scheduling, analytics synchronization, or performance-learning loop.

## 14. Recommended evolution

The existing architecture can evolve without replacing the application:

1. expose original-production jobs in the dashboard;
2. add reusable scene-template interfaces;
3. add optional face/object tracking for intelligent vertical crops;
4. expand visual-change scoring into face/object-aware crop guidance;
5. make Whisper model selection configurable;
6. evaluate an optional local semantic model only if it provides measured value beyond the bounded Codex adapter;
7. add additional approved discovery adapters;
8. connect platform publishing only after manual testing, rights review, credential design, and explicit approval.

The current architectural boundary remains:

```text
discover or author → generate locally → validate → human review → manual upload
```
