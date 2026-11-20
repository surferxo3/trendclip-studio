# ADR-004: Optional Semantic Analyzers

Status: accepted for implementation

Date: 2026-11-20

## Context

Deterministic audio, transcript, replay, and visual signals can locate potentially interesting events, but they cannot reliably decide whether a joke, reveal, failure, discovery, or reaction forms a complete story. Some users already have Codex, Claude Code, Ollama, LM Studio, or another compatible local service installed.

Invoking an installed coding-agent CLI directly is not a stable product foundation. CLIs differ in authentication, interactive behavior, permissions, model access, cost, output guarantees, version compatibility, and operating-system support. They may also be unavailable or intentionally disabled.

## Decision

1. The deterministic analyzer remains the required reference workflow and must produce usable drafts without an LLM or agent account.
2. TrendClip will define one provider-neutral, versioned semantic-analyzer contract before adding more provider implementations.
3. Optional analyzers receive bounded local JSON containing candidate identifiers, timestamped transcript excerpts, signal evidence, and requested editorial tasks. Raw credentials, cookies, unrelated files, and unrestricted workspace access are excluded.
4. Optional analyzers return schema-validated beat labels, completeness judgments, candidate ordering, confidence, warnings, and rationale. They do not download media, render files, or publish content.
5. Installed-agent adapters are disabled by default, detected explicitly, invoked with the narrowest available permissions, bounded by timeout/output/concurrency limits, and allowed to fail back to deterministic results.
6. Local-service adapters such as Ollama or an OpenAI-compatible loopback endpoint are implemented before broad agent-CLI support because their request/response contract is more stable.
7. An adapter is promoted in the UI only after it improves the shared quality benchmark. Availability is not evidence of quality.
8. The existing Codex adapter remains experimental until it implements the common contract and passes cross-platform compatibility tests.

## Consequences

- Users without an agent receive the complete core product.
- Users with suitable local tools can opt into semantic improvements without forcing dependencies on everyone else.
- Provider-specific authentication and subprocess behavior stay outside moment detection, rendering, and validation.
- TrendClip can compare deterministic, local-model, and agent-assisted output using the same evidence and evaluation set.

