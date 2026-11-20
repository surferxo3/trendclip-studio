# Original Video Renderer

## Purpose

Produce a repeatable, original 9:16 short from a reviewed topic configuration.

## Scope

Inputs: one JSON topic profile, the embedded original block typeface, and FFmpeg/ffprobe. Outputs: MP4, posting/provenance metadata JSON, and technical validation JSON. No external media, discovery, upload, or transcript.

## Security considerations

Strict configuration/layout limits, safe path resolution, no shell invocation, staged validation, rollback-protected export promotion, and local-only assets. See `docs/SECURITY.md`.

## Acceptance criteria

- 1080x1920 MP4, H.264 video, AAC audio, yuv420p, 15–30 seconds, 24–60 fps.
- Legible text within 90 px horizontal and 170 px vertical design margins.
- Configuration controls topic text, scene timings/colors, sources, disclosure, and posting metadata.
- A failed render or validation does not replace the prior coherent MP4/metadata/validation set.
- ffprobe evidence is saved and a failed check returns a non-zero CLI exit.

## Tests

Unit tests cover valid/invalid configuration, topic properties, layout/glyph bounds, path traversal, graph construction, config-driven disclosure, prior-export preservation, metadata, CLI behavior, absent FFmpeg, frame-rate checks, and probe success/failure. The release workflow also performs a real render, ffprobe validation, and representative frame inspection.

## Status

Implemented for the `gta6` profile in v0.1.0.

This document covers the original-graphic renderer only. The third-party review-draft workflow is documented in `local-dashboard-and-discovery.md` and `OPERATIONS.md`.

