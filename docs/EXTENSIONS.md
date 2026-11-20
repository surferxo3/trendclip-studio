# Extending TrendClip Studio

TrendClip is intentionally usable without an LLM and intentionally small enough for a developer or coding agent to extend locally. Extensions should preserve the local-only, manual-publishing boundary unless a fork clearly documents a different security model.

## Add a niche profile

Profiles live in `config/profiles.json`. Copy an existing entry, give it a unique lowercase slug, and set:

- `name`: user-facing label.
- `query`: default YouTube discovery query.
- `strategy`: one of `gaming`, `conversation`, `educational`, `comedy`, or `craft`.
- `freshness_hours`, `minimum_duration_seconds`, and `maximum_duration_seconds`.
- `include_terms` and `exclude_terms` for deterministic relevance filtering.

Run the profile tests after editing:

```bash
python -m unittest tests.test_v05_foundations.ProfileTests -v
```

The focused v0.5 dashboard intentionally exposes GTA 6 only. A fork may change `project_status()` in `trendclip/dashboard.py` to expose more validated profiles.

## Add a discovery source

A discovery adapter should return the normalized candidate fields already emitted by `trendclip.discovery`:

```json
{
  "title": "Example",
  "url": "https://www.youtube.com/watch?v=example",
  "source_name": "Creator",
  "published_at": "2026-11-21T00:00:00Z",
  "age_hours": 3.5,
  "views": 120000,
  "views_per_hour": 34285.7,
  "thumbnail": "https://i.ytimg.com/..."
}
```

Do not invent views, publication time, or velocity. Unknown measurements stay null. Network calls must be bounded, read-only, and restricted to documented hosts.

## Add a highlight strategy

Strategies live in `trendclip/highlight_strategies.py`. A strategy combines observable signal arrays and must return candidates with:

- start, end, and duration;
- raw ranking evidence and separate 0–10 editorial quality;
- component scores;
- a transcript excerpt;
- plain-language reasons and warnings.

Keep speech-boundary, payoff, context, overlap, and diversity gates. Add deterministic fixtures to `tests/test_v05_foundations.py`; a high energy spike alone is not proof of a good Short.

## Add a render layout

Layouts are validated by `RENDER_LAYOUTS` in `trendclip/media_pipeline.py`. A layout must produce 1080×1920 BGR frames, preserve relevant source content, leave mobile-safe caption space, and pass structural plus black/freeze/silence validation. Add a visual-difference test and a real synthetic encode smoke before exposing it in `trendclip/drafts.py`.

## Add a destination

Destination metadata is generated in `trendclip/export_package.py`. Add the destination to its allowlist and to the dashboard selection controls. Keep account authentication, uploading, scheduling, and analytics outside the core unless a fork explicitly takes responsibility for those credentials and side effects.

## Add an optional semantic analyzer

Follow `docs/decisions/ADR-004-optional-semantic-analyzers.md`. An analyzer must be disabled by default, receive a bounded non-secret payload, return schema-validated JSON, time out, and fall back to deterministic results. It may reorder or explain real candidates; it may not invent timestamps or become necessary for download, transcription, rendering, validation, or export.

## Verification checklist

Before proposing an extension:

```bash
python -m unittest discover -s tests -v
python -m compileall -q trendclip tests
node --check dashboard/app.js
python scripts/smoke_source_pipeline.py
```

Also update the relevant architecture, feature, operations, or decision document. Never commit downloaded media, model caches, browser sessions, logs, runtime state, or generated exports.

