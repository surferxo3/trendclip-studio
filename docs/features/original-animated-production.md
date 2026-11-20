# Original Animated Production

## Purpose

Create an original, narrated 50–60 second vertical explainer without downloaded third-party footage.

## Reused capabilities

- Existing FFmpeg H.264/AAC encoding and audio processing.
- Existing `ffprobe` validation and SHA-256 evidence.
- Existing OpenCV dependency and project-local output conventions.
- Existing structured JSONL log destination.

## Small extension

`trendclip.original_production` adds a reviewed script/scene configuration, Edge TTS narration, VTT-to-SRT export, continuous OpenCV animation, burned mobile captions, original-asset composition, thumbnail/contact-sheet generation, platform metadata, and a production report. The CLI exposes this as `trendclip produce-original`.

## Experiment 001 evidence

The first production is stored under `productions/experiment-001-agentic-commerce/`. Its final video is 57.333 seconds at 1080x1920 and 30 fps with H.264/yuv420p video and AAC audio. Validation passed. Publishing remains manual.
