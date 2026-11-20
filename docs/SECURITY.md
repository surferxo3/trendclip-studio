# Security Model

## Boundaries

TrendClip Studio performs local, foreground-only work. Discovery is read-only and source ingestion is limited to HTTPS YouTube URLs selected from the latest report. It does not publish, upload, schedule, or persist as a background service. When the visible Chrome-session switch is enabled, yt-dlp reads the current local Chrome YouTube session for that media job; TrendClip never receives, copies, or logs individual cookie values.

## Controls implemented

- Strict slug/date/config validation and bounded scene counts, text lengths, colors, duration, resolution, and frame rate.
- Resolved-path containment checks prevent output traversal outside the project.
- `subprocess` receives argument arrays with `shell=False` (the Python default).
- Text uses a bounded embedded glyph map and is rasterized into temporary PPM images before FFmpeg receives it.
- A staged MP4 is probed and hash-bound to its metadata before the coherent three-file export set is promoted; rollback preserves the prior set if promotion fails.
- Generated outputs and secrets are excluded by `.gitignore`.
- Media dependencies are pinned to the project-local `.venv`; FFmpeg/ffprobe and the installed Node runtime are invoked without a shell.
- Provenance and rights-review statements accompany every export.
- Dashboard binding is restricted to `127.0.0.1`/`localhost`; state-changing requests require a custom local-action header and reject non-loopback browser origins.
- Feed responses are capped at 2 MB, redirects are rechecked against the host allowlist, and XML entries are bounded before storage.
- Structured JSONL diagnostics are redacted and bounded; browser cookie values and command output containing them are never logged.

## Threats and residual risks

- yt-dlp, the EJS challenge solver, FFmpeg, OpenCV, and Whisper parse or transform downloaded media and are part of the local trusted computing base. Worker-process isolation limits native-library conflicts but is not a malware sandbox.
- The embedded typeface intentionally supports a bounded uppercase glyph set; configuration loading rejects unsupported or overflowing scene text.
- Factual correctness can drift after retrieval. Source references include retrieval dates; re-verify time-sensitive content before posting.
- Technical validation does not guarantee platform acceptance, trademark compliance, permission, accuracy, or audience suitability.
- The generated audio is intentionally simple and should be reviewed at comfortable volume before publishing.
- Public feed availability and structure can change. Discovery failures are reported rather than silently replaced with invented candidates.
- Candidate generation accepts only a URL already present in the latest saved discovery report, sanitizes untrusted headline text for the renderer, and records the citation in export metadata.
- Source-video ingestion requires a provenance record. Discovered videos are marked `third-party-review-draft`; owned, licensed, and campaign sources can carry stronger authorization records. The record is preserved in job state, provenance, and export metadata.
- Chrome-session use is off by default. Enabling access does not change the rights decision.
- Optional Codex tasks run only when explicitly enabled, in a temporary working directory with read-only mode, no API key environment value, a strict task/schema allowlist, bounded time/output/concurrency, and deterministic fallback. Remote text is delimited as untrusted data.
- Remote ingestion is restricted to HTTPS YouTube hosts, playlists are disabled, sources are stored under deterministic local job directories, and publishing remains disabled.
- A logged-in browser session can improve access but does not grant reuse rights. Disabling the switch prevents future yt-dlp jobs from requesting Chrome cookies; already-downloaded local source files remain until manually removed.
- Downloading and editing a source does not itself grant publishing rights; the user remains responsible for source permission and platform terms.

## Operational rules

Do not add new network hosts, executable downloads, token persistence, publishing, global dependencies, or background services without a separate design/security review and explicit approval. Treat remote repositories and all downloaded media as untrusted data.

