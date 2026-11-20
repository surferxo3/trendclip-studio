# ADR-003: Local dashboard with manual publishing

- Status: Accepted
- Date: 2026-11-19

## Context

The desired end state automates discovery, ranking, generation, validation, scheduling, publication, and tracking. During initial testing, the owner wants to upload manually to review quality and copyright risk before platform credentials or publishing actions are introduced.

## Decision

Add a loopback-only dashboard for discovery, explicit candidate selection, source download into a local review job, transcription, moment selection, generation, preview, validation, and export. Do not implement platform authentication, uploads, scheduling, or analytics. Discovered inputs are labeled as third-party review drafts without an ownership claim. Restricted YouTube access may use a visible Chrome-session switch whose cookie values are neither persisted nor logged.

## Consequences

The workflow is easier to control without expanding the current rights or credential boundary. “Fully automated” currently means the local preparation stages only. Direct publishing remains a separately reviewed future milestone after manual-upload testing succeeds.

