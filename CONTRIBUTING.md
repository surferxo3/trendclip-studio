# Contributing to TrendClip Studio

Thank you for helping make local video creation more accessible. TrendClip welcomes fixes, documentation improvements, new deterministic signals, layouts, profiles, destination metadata, and optional analyzer adapters.

## Before opening a change

1. Read `docs/PRODUCT-SCOPE.md`, `docs/ARCHITECTURE.md`, and `docs/EXTENSIONS.md`.
2. Keep the core workflow local, free, and independent of an LLM or hosted service.
3. Do not add automatic social posting, telemetry, credentials, or cloud storage to the core.
4. Do not commit downloaded media, generated videos, model caches, cookies, logs, or runtime state.
5. Add tests and update the relevant documentation for behavioral changes.

## Development setup

Run the setup launcher for your operating system, then:

```bash
python -m unittest discover -s tests -v
python -m compileall -q trendclip tests
node --check dashboard/app.js
python scripts/smoke_source_pipeline.py
```

Use the project-local `.venv` interpreter when the environment is not activated.

## Pull-request checklist

- The normal workflow still works without Codex, Claude, Ollama, or an API key.
- Errors shown to users are concise; diagnostics remain redacted.
- New paths, URLs, commands, and JSON fields are validated.
- Render changes pass structural and black/freeze/silence checks.
- Optional integrations are disabled by default and fail back safely.
- Documentation describes actual verified behavior rather than intended behavior.
- No third-party content or private data is included in fixtures.

See `docs/EXTENSIONS.md` for profile, discovery, scoring, layout, destination, and semantic-analyzer interfaces.

