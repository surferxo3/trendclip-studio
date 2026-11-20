# Local Dashboard and Discovery

## Purpose

Provide one local control surface for approved-source discovery, transparent ranking, video generation/validation, preview, and manual-upload tracking without enabling platform publishing.

## Inputs and outputs

- Inputs: reviewed topic/source JSON, recent YouTube results and approved public feeds, an explicitly selected URL, per-source reuse confirmation, and optionally the local Chrome YouTube session.
- Outputs: ignored discovery reports under `state/`, validated exports under `output/`, and ignored manual-upload tracking state.

## Security

The server binds only to loopback. POST operations require a local-action header and accept only loopback browser origins. Discovery is HTTPS-only and read-only. The Chrome-session option is explicit, locally remembered, and passed to yt-dlp only; cookie values are never persisted or logged. Publishing endpoints do not exist.

## Ranking

Recent YouTube results are ranked by observed views per hour; approved-feed fallbacks use relevance, freshness, and source reliability with unavailable measurements left null. The dashboard must not label either as proof of platform-wide trend status.

## Acceptance criteria

- Studio shows configured topics, the latest validated export, preview/download, selectable discovery candidates, and the manual-upload log.
- A selected saved candidate can be recorded as a third-party local review job, downloaded, transcribed, scored for strong moments, and turned into a selected vertical captioned draft.
- Export metadata preserves the source URL, publisher, selected timestamps, reasons for selection, provenance category, and validation digest.
- Discovery parses approved Atom/RSS data and filters unrelated entries.
- Missing measurement fields are never invented.
- Generation produces H.264/AAC 1080x1920 output with word captions, hook, and normalized audio, then runs the existing technical validator.
- YouTube, Facebook, TikTok, and scheduling remain disabled.
- Media dependencies stay inside the project-local `.venv`; the launcher uses that interpreter.

## Status

Expanded and verified in v0.5.0 with reusable niche profiles, automatic on-demand refresh, optional search, source provenance, browser session off by default, five explainable highlight strategies, durable/cancellable jobs with bounded concurrency and cached retry, complete export packages, optional bounded Codex tasks, 67 tests, and live loopback/visual checks. The normal GTA 6 flow discovers sources automatically and does not require URL entry. YouTube partial-metadata failures preserve usable candidates rather than blanking the list. Setup/start launchers and CI definitions now cover Windows, macOS, and Linux, while hosted CI and real-hardware release smoke records remain outstanding. Settings provides a bounded synthetic Codex check; candidate results expose editorial quality, warnings, and optional Codex rationale. Analysis now combines audio/transcript evidence with a low-resolution visual proxy, and balanced, punchy, and clean variations persist for review. Live streams/chat spikes, facecam-aware tracking, manual montage editing, post-reboot auto-resume, and cache retention controls remain.

