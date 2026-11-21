# TrendClip Studio

> Turn current GTA 6 videos into explainable, review-ready vertical clip drafts—locally, for free, without requiring an LLM or cloud account.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
[![Cross-platform tests](https://github.com/surferxo3/trendclip-studio/actions/workflows/tests.yml/badge.svg)](https://github.com/surferxo3/trendclip-studio/actions/workflows/tests.yml)
![Platforms](https://img.shields.io/badge/platforms-Windows%20%7C%20macOS%20%7C%20Linux-5FD6C8)
![License](https://img.shields.io/badge/license-MIT-F5C451)
![Publishing](https://img.shields.io/badge/publishing-manual%20only-98A2B3)
![LLM](https://img.shields.io/badge/LLM-optional-FF5AA5)

TrendClip Studio is a free, local-first GTA 6 clipping pipeline that discovers current source videos, transcribes them, ranks promising moments, and creates validated vertical captioned drafts for manual review and publishing.

Version 0.5.0 provides the foundation: current YouTube discovery ranked by observed views/hour, optional logged-in Chrome access with consent, audio plus a low-resolution visual-analysis proxy, Faster Whisper word timestamps, explainable editorial scoring, three automatic draft recommendations, selected-range full-quality download, three distinct vertical treatments, word captions, −14 LUFS normalization, persistent variation exports, export packages, and technical/content validation. Final publishing remains manual.

## Why TrendClip exists

Most automated clipping products are paid, cloud-hosted, opaque, or tied to an AI subscription. TrendClip takes a different approach:

- **Free and forkable:** MIT licensed and designed as a reusable developer foundation.
- **Local-first:** media, transcripts, jobs, logs, and exports remain on your computer.
- **No mandatory LLM:** deterministic discovery, transcription, scoring, rendering, and validation work independently.
- **Explainable:** every candidate exposes evidence, editorial quality, transcript context, and uncertainty warnings.
- **Creator-controlled:** TrendClip prepares drafts and metadata; you review and upload manually.
- **Honest about quality:** it proposes candidate moments—it does not promise virality, copyright clearance, monetization, or platform acceptance.

## What it can do

| Stage | Capability |
|---|---|
| Discover | Searches current YouTube results for GTA 6 and orders measurable candidates using views per hour, freshness, relevance, and duration limits. |
| Access | Uses anonymous yt-dlp access by default, with an optional per-job Chrome-session switch when YouTube requires sign-in. |
| Analyze | Downloads audio plus a lightweight 240p visual proxy; transcribes locally with Faster Whisper and samples replay, speech, loudness, motion, and shot-change evidence. |
| Select | Scores clean beginnings/endings, hooks, payoff, context, event coherence, replay activity, emphasis, and gaming signals. |
| Draft | Automatically recommends **Best story**, **High energy**, and **Quick hit**—no timestamp selection required in the normal flow. |
| Render | Downloads only the chosen range at full quality and renders 1080×1920 H.264/AAC with word captions, a hook, and −14 LUFS normalization. |
| Vary | Provides distinct **Balanced story**, **Punchy action**, and **Clean focus** treatments and preserves each generated version. |
| Validate | Checks decoding, container, codecs, dimensions, frame rate, pixel format, duration, black frames, frozen spans, and long silence. |
| Package | Creates captions, thumbnail, provenance, checksums, and destination-specific metadata for selected platforms. |
| Review | Plays the result in the local dashboard and provides direct downloads. Nothing is uploaded automatically. |

## How it works

```text
Current YouTube discovery
          │
          ▼
Choose one listed source
          │
          ▼
Audio + 240p visual proxy
          │
          ├── Faster Whisper word timestamps
          ├── loudness and speech emphasis
          ├── YouTube replay evidence when available
          └── motion and shot-change samples
          │
          ▼
Explainable candidate beats
          │
          ▼
Best story · High energy · Quick hit
          │
          ▼
Selected range downloaded at full quality
          │
          ▼
OpenCV reframing/captions + FFmpeg encode/audio
          │
          ▼
Structural and content-quality validation
          │
          ▼
Local review package for manual upload
```

## Quick start

TrendClip runs on Windows, macOS, and Linux in a private project-local Python environment. It does not require Codex, Claude, an API key, or an LLM account.

### System prerequisites

Install these once before running TrendClip Setup:

| Requirement | macOS | Windows | Ubuntu/Debian |
|---|---|---|---|
| Python 3.10+ | `brew install python` or python.org | python.org or Microsoft Store | `sudo apt install python3 python3-venv` |
| FFmpeg + ffprobe | `brew install ffmpeg` | `winget install --id Gyan.FFmpeg -e` | `sudo apt install ffmpeg` |
| Node.js LTS | `brew install node` | `winget install OpenJS.NodeJS.LTS` | Install the current Node.js LTS package |

FFmpeg performs media processing. Node.js enables reliable YouTube challenge handling through yt-dlp. After installing a Windows prerequisite, open a new terminal before continuing.

### One-time setup

- macOS: double-click **Setup TrendClip Studio.command**.
- Windows: double-click **Setup TrendClip Studio.bat**.
- Linux: run `./setup-trendclip.sh`.

Setup creates `.venv`, installs all Python packages there, and runs the system doctor. It does not silently install operating-system software or request administrator access. The Whisper speech model downloads automatically on the first analysis and is then cached locally.

### Start Studio

- macOS: double-click **Start TrendClip Studio.command**.
- Windows: double-click **Start TrendClip Studio.bat** or run **Start TrendClip Studio.ps1**.
- Linux: run `./start-trendclip.sh`.

The dashboard opens when the local server is ready. Source refresh continues in the background.

### Terminal setup and start

Users who prefer commands can run the same workflow manually.

macOS/Linux:

```bash
./setup-trendclip.sh
./.venv/bin/python -m trendclip studio
```

Windows PowerShell:

```powershell
& ".\Setup TrendClip Studio.ps1"
.\.venv\Scripts\python.exe -m trendclip studio
```

Useful terminal commands:

```bash
# Check dependencies and local readiness
python -m trendclip doctor

# Start Studio and open the browser
python -m trendclip studio --host 127.0.0.1 --port 8765

# Start only the server; open http://127.0.0.1:8765 yourself
python -m trendclip dashboard --host 127.0.0.1 --port 8765

# Run the complete automated test suite
python -m unittest discover -s tests -v

# Search configured read-only discovery sources
python -m trendclip discover --topic gta6

# Render the configuration-driven graphical fallback
python -m trendclip render --topic gta6 --mode original --date 2026-11-21

# Render the original agentic-commerce experiment
python -m trendclip produce-original

# Score adjudicated creator-quality evidence
python -m trendclip benchmark --manifest benchmarks/my-reviewed-samples.json
```

Run commands with the `.venv` interpreter shown above, or activate the environment first and use `python`.

Studio starts at [http://127.0.0.1:8765](http://127.0.0.1:8765). Choose a discovered source and analyze it. TrendClip prepares Best story, High energy, and Quick hit drafts and selects Best story automatically; choosing another draft is optional. Analysis downloads audio and a small visual proxy for motion/shot signals, while only the chosen range is downloaded at full quality for rendering. The first analysis downloads the Whisper `small` speech model; later runs reuse the local cache. The server binds only to the local loopback interface and stops with `Ctrl+C`.

### First-run workflow

1. Review the discovered GTA 6 videos. Use **Refresh stories** for current results.
2. Select a source. You normally do not paste a URL.
3. Leave **Chrome YouTube session** off unless Studio says that source requires sign-in.
4. Choose **Download and find the best moments**.
5. Review the three explained drafts. Best story is selected automatically.
6. Edit the opening hook if desired.
7. Select YouTube, Facebook, and/or TikTok for publishing metadata.
8. Create the recommended or selected draft.
9. Watch the validated result, download it, and decide whether to upload it manually.

Long videos and first-time transcription can take several minutes on CPU. The Processing section shows durable job status and safe error messages.

The **Chrome YouTube session** switch is off by default and remembered locally only when you enable it. When enabled, the downloader asks Chrome for the current session for that job only. Cookie values are never copied into TrendClip state or logs. Chrome sign-in only provides access to videos that reject anonymous requests; it does not establish ownership or publication rights.

Optional Codex assistance is off by default. If the Codex CLI is installed and signed in, Settings can enable a bounded experiment for semantic reranking and platform-copy drafts. Use **Test Codex safely** to run a synthetic three-candidate check before analyzing real media. It may use the user's Codex plan allowance. Deterministic discovery, download, transcription, scoring, rendering, validation, and export do not depend on it.

Operational events and redacted errors are written as JSON lines to `state/logs/studio.log`. See [Operations and troubleshooting](docs/OPERATIONS.md) for checks and recovery steps.

The render command creates:

```text
output/gta6/2026-11-19/
├── clip-001.mp4
├── clip-001.json
├── clip-best-story.mp4
├── clip-best-story.json
├── validation-best-story.json
├── captions.srt
├── thumbnail.png
├── platform-metadata.json
├── provenance.json
├── export-manifest.json
└── validation.json
```

Preview on macOS with Finder/Quick Look, or explicitly with:

```bash
open output/gta6/2026-11-19/clip-001.mp4
```

Opening a GUI is intentionally left to the user. The renderer never uploads or publishes content.

## How moment scoring works

TrendClip deliberately separates **signal strength** from **editorial quality**.

Signal evidence proposes potentially interesting ranges:

- sudden audio-energy changes;
- speech density and emphasis language;
- YouTube most-replayed heat when available;
- low-resolution motion and shot changes;
- strategy-specific gaming, reaction, conversation, education, comedy, or craft cues.

Editorial scoring asks whether the range works as a Short:

- Does it begin at a clean speech boundary?
- Is the setup understandable?
- Is there a hook or meaningful event?
- Does the clip contain a payoff or complete ending?
- Is it dependent on omitted context?
- Does it duplicate another candidate?

The user-facing quality score is bounded from 0–10 and exposes its components and warnings. A high number is not a guaranteed “viral score.” Read [Moment Selection and Assembly](docs/MOMENT-SELECTION-AND-ASSEMBLY.md) and [Quality Benchmark](docs/QUALITY-BENCHMARK.md) for the complete model.

## Privacy and safety

- The dashboard listens only on `127.0.0.1`/`localhost`.
- There is no telemetry, signup, cloud database, social OAuth, or automatic upload.
- Runtime state, media, `.venv`, logs, caches, and generated output are excluded from Git.
- Paths, request bodies, topics, dates, URLs, and destination choices are validated.
- Dashboard mutations require a same-origin local action header.
- Error logs redact project/home paths and common secret labels.
- Third-party sources are labeled as local review drafts rather than falsely marked creator-owned.

Read [Security](docs/SECURITY.md) for the complete threat boundary.

## Automation boundary

The Studio can discover and rank recent YouTube candidates, ingest a selected source as a local review job, transcribe it, combine replay/audio/speech/motion evidence, recommend three editorial drafts, render three visibly different vertical styles, preserve generated variations, validate content and structure, and preview/download the export. The six-job Windows/macOS/Linux hosted CI matrix passes; real-hardware Windows/Linux release smoke tests, authorized human benchmark media, and facecam-aware subject tracking remain release-quality gaps. Automatic posting, scheduling, and analytics are deliberately out of scope. See [Product Scope](docs/PRODUCT-SCOPE.md), [Quality Benchmark](docs/QUALITY-BENCHMARK.md), and [Reference Capability Gap](docs/REFERENCE-GAP.md).

Run the evidence-based quality score after completing a local benchmark manifest:

```bash
python -m trendclip benchmark --manifest benchmarks/my-reviewed-samples.json
```

The command returns a non-zero result when targets, platform evidence, or critical gates are missing. The example manifest is intentionally not release evidence.

## Platform support and verification

| Platform | Setup/start launcher | Automated CI definition | Executed in this release workspace |
|---|---:|---:|---:|
| macOS | Yes | Python 3.10 and 3.12 | Yes |
| Windows | Yes, Batch + PowerShell | Python 3.10 and 3.12 | Hosted CI passed; real-hardware smoke pending |
| Linux | Yes, POSIX shell | Python 3.10 and 3.12 | Hosted CI passed; real-hardware smoke pending |

The implementation avoids shell-built FFmpeg strings and uses `pathlib`, Python subprocess argument lists, standard JSON, OpenCV, and FFmpeg APIs. GitHub Actions passed all six OS/Python combinations on November 21, 2026. This proves installation, unit tests, compilation, browser JavaScript syntax, and launcher parsing in hosted Windows, macOS, and Linux environments; real-hardware media-pipeline smoke tests remain a separate release check.

## Architecture at a glance

| Module | Responsibility |
|---|---|
| `trendclip.discovery` | YouTube/feed discovery, normalized evidence, freshness and views-per-hour ordering. |
| `trendclip.media_pipeline` | yt-dlp ingestion, audio/proxy preparation, Whisper transcription, OpenCV rendering, and FFmpeg encoding. |
| `trendclip.highlight_strategies` | Explainable signal weights, boundaries, completeness, quality components, and warnings. |
| `trendclip.drafts` | Best story, High energy, Quick hit, and their visual treatments. |
| `trendclip.validate` | ffprobe structure plus black, freeze, and silence detection. |
| `trendclip.export_package` | Captions, thumbnail, provenance, destination metadata, and checksummed manifests. |
| `trendclip.jobs` | Durable atomic job stages, history, cancellation, and retry state. |
| `trendclip.dashboard` | Loopback-only UI/API, media streaming, settings, and redacted diagnostics. |
| `trendclip.codex_adapter` | Optional bounded schema-validated semantic assistance. |
| `trendclip.benchmark` | Human-review scorecard and critical release gates. |

See [Architecture](docs/ARCHITECTURE.md) and [Product Architecture](docs/PRODUCT-ARCHITECTURE.md) for diagrams and detailed data flow.

## Cardboard, MCP editors, and other tools

[Cardboard](https://www.cardboard.ai/mcp) demonstrates a strong conversational editing experience: timeline operations, captions, reframing, moment extraction, previews, and exports through ChatGPT and Claude tools. TrendClip takes inspiration from its plain-language actions, persistent projects, visible progress, and editable results—but does not depend on Cardboard.

Cardboard’s MCP workflow requires a Cardboard account, uses Cardboard plan credits, and performs editing in its cloud. Its local agent-connected desktop workflow is currently specific to Apple-silicon Macs. TrendClip’s promise is different: a free, independently runnable, local-first core for Windows, macOS, and Linux. A community extension may export TrendClip drafts into Cardboard or another editor, but that integration must remain optional.

See [Competitive Review](docs/COMPETITIVE-REVIEW.md) for the GTA 6 clippers, local-model tools, and agent-driven editing projects reviewed during development.

## Testing and the 10/10 target

The current recorded local evidence includes:

- 67 passing unit/integration tests;
- Python compilation, JavaScript syntax, POSIX shell, and zsh checks, with a PowerShell parser check defined for Windows CI;
- a passing dependency doctor and `pip check`;
- loopback dashboard/API checks;
- desktop and 390×844 responsive visual inspection;
- a real synthetic-media 1080×1920 H.264/AAC encode;
- no long black, frozen, or silent spans in the smoke export;
- a complete captions/thumbnail/provenance/metadata/manifest package;
- a bounded authenticated Codex synthetic-ranking smoke test.

Run the real encoding smoke locally:

```bash
python scripts/smoke_source_pipeline.py
```

TrendClip does not award itself 10/10 because the test suite passes. A valid perfect score requires representative authorized media, two independent reviewers per sample, every documented usefulness and quality target, passing Windows/macOS/Linux evidence, and no critical failure. The benchmark command calculates that result and refuses release readiness while evidence is missing.

## Original animated productions

The production renderer creates original 50–60 second explainers from a reviewed script and scene plan using OpenCV motion graphics, an original generated illustration, Edge TTS narration, timed SRT captions, FFmpeg encoding/audio mixing, and the existing validator. Run the first experiment with:

```bash
python3 -m trendclip produce-original
```

Its review package is written under `productions/experiment-001-agentic-commerce/output/`. Nothing is uploaded.

## Add another topic

Copy `config/topics/gta6.json`, change its slug/content/sources, and retain the validated schema. The shared renderer reads all scene text, timing, colors, source references, and posting metadata from configuration. See [Architecture](docs/ARCHITECTURE.md), [Extending TrendClip](docs/EXTENSIONS.md), and the [video feature specification](docs/features/original-video-renderer.md).

## Extending TrendClip

TrendClip is designed as a building block. A fork can add a niche profile, discovery adapter, deterministic signal, highlight strategy, render layout, caption treatment, metadata destination, optional local model, or downstream publishing module.

The default workflow must continue to work without Codex, Claude, Ollama, an API key, or a paid provider. Start with [Extending TrendClip](docs/EXTENSIONS.md), then read [ADR-004](docs/decisions/ADR-004-optional-semantic-analyzers.md) before adding an agent or model adapter.

## Troubleshooting

### A prerequisite is missing

Install Python, FFmpeg/ffprobe, or Node.js from the requirements table, open a new terminal, rerun Setup, then run `python -m trendclip doctor`.

### The browser does not open

The server may still be running. Open [http://127.0.0.1:8765](http://127.0.0.1:8765) manually. Use `python -m trendclip dashboard` when you intentionally do not want automatic browser launch.

### YouTube requests sign-in

Open YouTube in Chrome, confirm you are signed in, enable **Chrome YouTube session**, and retry. If YouTube still rejects the session, choose another source. Never export cookies into this project.

### Analysis is slow

The first analysis downloads the Whisper model. CPU transcription of long material can take several minutes; later runs reuse cached model and job data.

### Refresh returns no new videos

TrendClip preserves the last useful list when a temporary YouTube metadata failure returns an empty result. Check Processing and the redacted `state/logs/studio.log` record.

### A render fails validation

The failed draft is not promoted over a previous valid export. Review its validation errors and job history, then retry another draft or source.

See [Operations and Troubleshooting](docs/OPERATIONS.md) for detailed recovery steps.

## Contributing

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) and [Extending TrendClip](docs/EXTENSIONS.md). Please keep the core local, free, deterministic, testable, and honest about third-party media.

Good first contributions include authorized synthetic fixtures, facecam-aware framing, manual montage controls, cache-retention controls, additional deterministic gaming signals, accessibility improvements, and Windows/Linux smoke-test records.

## Project scope

TrendClip intentionally does **not** include cloud hosting, multi-user accounts, social OAuth, automatic posting, scheduling, analytics, guaranteed virality, or guaranteed rights clearance. Forks may add those features, but they require separate security and product decisions.

## License

TrendClip Studio is available under the [MIT License](LICENSE).

## Product name

- Product/project: **TrendClip Studio**
- Python distribution: `trendclip-studio`
- Python package and CLI: `trendclip`
- Workspace directory: `trendclip-studio`

