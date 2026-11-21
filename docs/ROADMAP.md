# Roadmap

| Milestone | Status | Acceptance summary |
|---|---|---|
| M0 — Safe initialization | Complete | Named project, security boundary, architecture, context, references, and decisions exist. |
| M1 — First working video | Complete | Reusable renderer produces a real GTA VI MP4, metadata, and passing technical validation; tests pass. |
| M2 — Reusable video pipeline | Complete for recorded clips | Studio uses audio plus a 240p visual proxy, deferred selected-range full-quality download, and creates validated 1080x1920 source clips with hooks, word captions, three visual treatments, persistent variations, H.264/AAC encoding, normalized audio, and optional authenticated source access. Translation remains optional future work. |
| M3 — Trend discovery | Initial implementation | Recent YouTube search ranked by observed views/hour, approved-feed fallback, normalized candidates, saved reports, and dashboard view exist. Broader cross-platform trend evidence remains. |
| M3.5 — Local control dashboard | Complete | Task-focused loopback-only Studio supports refresh, story selection, generation, preview/download, validation status, and manual-upload tracking. |
| M4 — Highlight extraction | Complete for deterministic recorded-video baseline | YouTube audio/proxy download (anonymous or Chrome session), Node challenge solving, Whisper transcription, loudness/emphasis/replay/motion scoring, speech-aware boundaries, editorial-quality warnings, three automatic draft recommendations, selected-range download, and vertical export exist. Chat-spike scoring, deeper semantic vision, and facecam detection remain optional enhancements. |
| M5 — Reusable foundation | Complete | Reusable profiles, discovery filters, five highlight strategies, source provenance, and complete local export packages. |
| M6 — Focused GTA 6 local product | Implementation complete; evidence pending | Automatic GTA 6 discovery, simplified source selection, Best story/High energy/Quick hit recommendations, stronger gaming-event scoring, three visibly different persistent render variations, preview/download, destination selection, and YouTube/Facebook/TikTok metadata exist. Authorized creator benchmark results remain. |
| M7 — Cross-platform GitHub release | In progress | Public MIT repository, Windows/macOS/Linux setup and start launchers, actionable startup doctor, contribution/extension guides, and all six hosted Python 3.10/3.12 jobs pass. A packaged release and Windows/Linux real-hardware media-pipeline smoke records remain. |
| M5.1 — Reliability controls | In progress | Durable stages, bounded concurrency, cancellation, cached retry, and redacted logs are complete; user-controlled cache retention and post-reboot auto-resume remain. |
| M5.2 — Optional Codex assistance | Implemented, disabled by default | Bounded schema-validated semantic reranking and publishing drafts with deterministic fallback; no pipeline dependency. |
| M8 — Optional publishing automation | Deferred | Requires separate approval after manual-upload tests; no OAuth, scheduling, analytics, or uploading exists now. |

“Complete” reflects repository implementation and recorded local verification, not guaranteed acceptance by any social platform.

