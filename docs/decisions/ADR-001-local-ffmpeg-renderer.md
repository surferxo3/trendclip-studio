# ADR-001: Local FFmpeg renderer

- Status: Accepted for original-graphic mode; extended by the source-clipping pipeline
- Date: 2026-11-19

## Context

The first milestone needs a real vertical video today while preserving a reusable, dependency-light architecture and strict MacBook security boundary.

## Decision

Use standard-library Python to validate configuration and rasterize original PPM scenes with an embedded typeface, then invoke the existing FFmpeg/ffprobe binaries. Keep all topic content outside renderer code. Produce local exports only.

## Consequences

The original renderer remains dependency-light and useful as a safe fallback. The later source-clipping mode adds project-local Python media packages, but final encoding and validation still use FFmpeg/ffprobe.

