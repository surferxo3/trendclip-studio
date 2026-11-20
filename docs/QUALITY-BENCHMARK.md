# TrendClip Quality Benchmark

## Why this exists

TrendClip does not earn a high quality rating by returning large numeric scores. A trustworthy system gives weak moments low scores and proves that its top results are useful through repeatable evaluation.

The target is a measured creator-product score of at least **9.0/10**, with no critical workflow or render failure. A claimed 10/10 requires independent testing across representative sources and operating systems; it is not a label applied by the implementation team.

The repository includes `benchmarks/manifest.example.json` and an executable scorer:

```bash
python -m trendclip benchmark --manifest benchmarks/my-reviewed-samples.json
```

Every sample requires two reviewers and adjudicated booleans for each scorecard dimension. The command exits with status 2 until all release targets and critical gates pass. The synthetic example deliberately lacks cross-platform evidence and must not be used as a release claim.

## Evaluation set

Create a versioned local benchmark manifest containing permitted GTA/gameplay samples with:

- Source identifier and content type.
- Duration, language, facecam/layout type, and audio conditions.
- Human-marked event ranges.
- Hook, setup, action, payoff, reaction, and ending labels.
- Context-dependence, duplication, framing, and technical warnings.
- Two independent reviewer ratings plus an adjudicated result.

Do not commit third-party video files. The public repository may include synthetic fixtures and manifest schemas; evaluators supply or authorize real media locally.

## Product scorecard

| Dimension | Weight | Release target |
|---|---:|---:|
| Top-three usefulness | 25% | At least one publishable draft for 90% of benchmark sources |
| Narrative completeness | 20% | At least 85% of drafts understandable without omitted context |
| Boundary and caption accuracy | 15% | At least 95% without clipped speech or material caption drift |
| Visual framing | 10% | At least 95% keep the relevant gameplay/face region visible |
| Technical reliability | 10% | 100% of accepted exports decode and pass validation |
| First-time usability | 10% | At least 90% task completion without terminal assistance |
| Cross-platform operation | 5% | Verified smoke test on Windows, macOS, and Linux |
| Explainability and control | 5% | Every draft has evidence, warnings, and editable boundaries |

No aggregate score may hide a critical failure. Export corruption, silent audio, missing captions, unsafe path handling, secret leakage, or an unusable primary workflow blocks release regardless of the weighted total.

## Moment evaluation

The deterministic analyzer produces two distinct measurements:

1. **Signal evidence** — loudness change, replay/chat activity, speech emphasis, motion/shot change, and gaming-event evidence.
2. **Editorial quality** — clean start, clean ending, hook, payoff, context completeness, and event coherence.

Signal evidence proposes moments. Editorial gates decide whether they are usable. The user-facing quality score is bounded to 0–10 and must expose its components and uncertainty. It must never be called a guaranteed virality score.

## Analyzer comparison

Every optional analyzer receives the same bounded candidate payload and returns the same versioned result schema. Compare deterministic, local-model, and agent-assisted results using:

- Precision at 3 for human-approved moments.
- Normalized discounted cumulative gain for candidate ordering.
- Boundary error in seconds.
- Complete-story acceptance rate.
- Duplicate candidate rate.
- Runtime, peak memory, storage, and external cost.
- Invalid-output, timeout, and fallback rate.

An optional analyzer is promoted in the UI only when it improves the benchmark without weakening privacy, reliability, or fallback behavior.

## Milestones

1. Synthetic deterministic tests for sentence boundaries, context warnings, payoff evidence, and deduplication.
2. Local benchmark manifest and reviewer rubric.
3. Three automatically assembled deterministic drafts.
4. Rendered-output QA: decode, black/frozen frames, audio continuity, captions, and crop checks.
5. Provider-neutral semantic analyzer contract.
6. Optional local model adapter.
7. Optional installed-agent adapters, individually detected and disabled by default.
8. Real cross-platform and creator evaluation before publishing a quality score.

