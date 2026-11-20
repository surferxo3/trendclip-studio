# TrendClip Studio — GTA 6 Product Scope

## Product promise

TrendClip Studio is a free, open-source, local-first GTA 6 clip maker. It discovers current videos, helps the user choose a source, finds promising moments, creates several vertical clip drafts, and exports everything needed for manual publishing.

It is a reusable developer building block, not a hosted SaaS. Users may extend it with Codex, another coding agent, a local model, or their own adapters, but the core workflow must not require a paid API or an LLM account.

## Version 1 workflow

1. Discover recent and fast-growing GTA 6 videos automatically.
2. Show a clear list with thumbnail, title, channel, age, views, and observed views per hour.
3. Let the user select a video; no URL entry is required in the normal flow.
4. Download locally with yt-dlp.
5. Ask for browser-cookie consent only when a video requires a logged-in session; cookie values are never persisted or logged.
6. Decode audio and media signals with FFmpeg.
7. Transcribe speech locally with Faster Whisper.
8. Detect and label candidate story beats using explainable audio, transcript, replay, motion, completeness, and gaming-event signals.
9. Automatically assemble three coherent drafts while retaining single-highlight and user-selected montage modes.
10. Let the user inspect thumbnails, transcript excerpts, score reasons, surrounding context, and adjustable start/end points.
11. Render multiple 9:16 variations with OpenCV and FFmpeg, including captions, hook text, layout choices, optional credit, and optional watermark.
12. Validate each result and let the user preview and download it.
13. Generate platform-specific title, description/caption, hashtags/tags, thumbnail, captions, provenance, and technical metadata for selected destinations.

## Supported destinations

Version 1 targets YouTube Shorts, Facebook Reels, and TikTok. Destination support is a metadata/export choice only; TrendClip does not connect accounts or publish content. The adapter schema must allow Instagram Reels and other destinations to be added later without changing the media pipeline.

## Local and cross-platform requirements

- Windows, macOS, and Linux support.
- One primary command that starts the local server and opens the browser.
- Small OS-specific launchers may wrap that command.
- A startup doctor checks Python, FFmpeg/ffprobe, yt-dlp, model availability, writable storage, and browser-cookie capability.
- CPU operation is required; GPU acceleration is optional.
- All project state, downloaded media, models, logs, and exports remain local.
- No telemetry, signup, cloud database, or mandatory external API.

## Highlight scoring

The default scorer must work without a general-purpose LLM. It combines observable signals such as freshness and view velocity for discovery, then loudness changes, speech density, emphasis language, YouTube replay data when available, visual motion/cuts, and gaming-specific events for moment ranking. Every proposed moment exposes its component scores.

Optional analyzers may use Ollama, Codex, or another provider through a documented interface. They enhance semantic judgment but cannot become a requirement for the default workflow. The product must call results “candidate moments” rather than promise virality.

## Extensibility

- Profile interface for niches and games.
- Discovery-source adapter interface.
- Highlight-signal/scorer interface.
- Renderer/layout/effect interface.
- Metadata-destination adapter interface.
- Optional agent/LLM adapter interface.
- Versioned JSON job, analysis, and export schemas.
- Documented CLI commands so coding agents can compose the pipeline.

## Explicitly out of scope

- Cloud hosting or multi-user accounts.
- Automatic posting, scheduling, OAuth connections, or social-account storage.
- Performance monitoring or social analytics.
- Guaranteed virality, monetization, copyright clearance, or platform acceptance.
- Paid providers in the default path.
- Campaign discovery and payout tracking in the core application.

## GitHub release requirements

- Add an explicit open-source license before public release.
- Provide installation and troubleshooting instructions for all three operating systems.
- Run unit and integration tests on a Windows/macOS/Linux CI matrix.
- Include a small provenance notice without forcing users to make false ownership claims.
- Do not commit downloaded videos, browser cookies, model caches, logs, or generated exports.
- Publish an extension guide and sample plugin/profile.

## Version 1 acceptance criteria

A new user on a supported desktop OS can install the project, open one local dashboard, refresh GTA 6 discovery, select a listed video, generate at least three ranked candidate moments and at least two visibly different vertical drafts, preview them, and download a validated package with captions, thumbnail, provenance, and metadata for YouTube, Facebook, and TikTok—without paying for an API or using an LLM account.
