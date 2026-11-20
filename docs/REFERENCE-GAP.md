# Reference Capability Gap

Reviewed through 2026-11-20 from the public `Bodila51/gtavi-claudecode` implementation as untrusted reference data. Its scripts and agent instructions were not executed. Version 0.5 generalizes its strongest recorded-video ideas into niche profiles, strategy modules, explicit rights, durable jobs, and complete local exports.

| Capability claimed by reference | TrendClip Studio status |
|---|---|
| Videos from the last 24 hours ranked by views/hour | Implemented as bounded recent YouTube search ranked by observed views/hour, with official-feed fallback. Studio currently uses a 48-hour window to keep the UI useful when upload volume is low. |
| Live-stream discovery ranked by viewers | Not implemented. |
| Download selected source videos/streams | Implemented for selected YouTube videos as provenance-labeled local review jobs, with optional consent-based Chrome access and JS challenge solving; live streams remain. |
| Detect moments using loudness, hype words, most-replayed, and chat spikes | Loudness, hype words, speech activity, low-resolution motion/shot evidence, and available YouTube replay data implemented. Chat spikes remain. |
| Record live streams and cut on chat spikes | Not implemented. |
| Extract real 15–40 second source clips | Implemented for validated 7–30 second selectable moments. |
| Word-level captions, hooks, credits, facecam layouts, -14 LUFS | Captions, hook, source metadata, balanced/punch/clean vertical layouts, and −14 LUFS implemented. Facecam-aware tracking remains. |
| Campaign discovery/rule validation | Not implemented. |
| Multi-language captions and optional TTS | Original-production TTS exists; multi-language source clipping is not implemented. |
| Learning loop using real post performance | Manual upload tracking only; platform metrics are not connected. |
| Automatic platform publishing | Neither project publishes automatically by default; TrendClip explicitly keeps publishing disabled during manual testing. |

## Remaining parity work

The core recorded-video path is now multi-niche. Remaining parity work is live YouTube/Twitch/Kick discovery and capture, chat-spike detection, facecam/reaction layouts, campaign discovery and validation, translation, performance learning, worker cancellation/resume, and cache retention.

## Recommended parity order

1. Add live-stream discovery while continuing to tune the implemented views-per-hour radar.
2. Add chat replay/spike scoring and live segmented recording.
3. Add facecam/react layout detection and additional crop controls.
4. Add campaign rules, translation/TTS, and creator workflows.
5. Add performance tracking.
6. Only after successful manual testing, add separately approved platform OAuth, scheduling, and publishing adapters.

