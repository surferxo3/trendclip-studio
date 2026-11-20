# UI/UX Direction

## Assessment of the current interface

The current dashboard is functional and visually consistent, but it resembles a generic internal admin panel more than a polished creator tool. Its strongest qualities are the restrained dark palette, visible workflow stages, and clear local/manual-publishing status. Its weaknesses are small typography, excessive boxed panels, empty space, technical language, and a workflow centered on system stages rather than video decisions.

Current assessment:

- Visual consistency: 7/10
- Clarity for a first-time creator: 5/10
- Editing confidence: 4/10
- Competitive creator-tool polish: 5/10

Changing colors alone will not solve the main problem. The information architecture must shift from “choose a technical operation” to “compare ready drafts and understand why they work.”

## Design character

TrendClip should feel like a calm, modern creator workstation—not a neon gaming dashboard and not enterprise administration software.

- Dark neutral canvas suitable for video preview.
- One mint/teal action color.
- Warm amber only for uncertainty or review warnings.
- Red only for actual failures.
- Large preview imagery and readable 14–16 px body text.
- Fewer borders; use spacing, surface contrast, and restrained shadows.
- Sentence case instead of excessive uppercase labels.
- No GTA artwork, logos, or trademark-dependent visual identity in the application shell.

Suggested tokens:

| Role | Color |
|---|---|
| Canvas | `#0B0D10` |
| Primary surface | `#13171C` |
| Elevated surface | `#191E25` |
| Main text | `#F5F7FA` |
| Secondary text | `#9AA4B2` |
| Primary action | `#67DCC4` |
| Success | `#65D88B` |
| Review/uncertainty | `#F4B740` |
| Error | `#F97066` |

## Primary navigation

Use four destinations only:

1. **Discover** — current GTA 6 sources and trend evidence.
2. **Drafts** — automatically assembled and user-created clip drafts.
3. **Exports** — validated downloadable packages.
4. **Settings** — local models, Chrome-session consent, storage, and optional agent integrations.

Processing status belongs in a compact global job drawer rather than a primary navigation destination once the workflow is stable.

## Main workflow

### Discover

- Content-first video rows or cards with large thumbnails.
- Title, channel, age, views/hour, duration, and source availability.
- One clear primary action: **Analyze this video**.
- Filters remain secondary and collapsed by default.

### Draft comparison

Show three large preview cards: Best story, High energy, and Quick hit. Each card includes duration, beat strip, hook, confidence, reasons, warnings, and **Preview** / **Open editor** actions.

Candidate signals and raw scores stay inside **Why these moments?**. The normal user should not need to interpret timestamps or formulas.

### Editor

- Video preview at useful size.
- Compact beat/timeline strip.
- Transcript synchronized to playback.
- Start/end handles and beat include/exclude controls.
- Layout, captions, hook, credit, and watermark controls.
- Destination selection for YouTube, Facebook, and TikTok.
- Persistent **Generate variations** action.

### Export

- Side-by-side variation previews.
- Technical validation and provenance status.
- Editable platform copy and thumbnail.
- One **Download package** action.
- No upload, scheduling, or analytics controls.

## Interaction principles

- Show progressive feedback for download, transcription, analysis, rendering, and validation.
- Preserve completed work when a later stage fails.
- Errors provide one plain-language cause, one recovery action, and a link to technical details.
- Keyboard focus, contrast, reduced motion, and 44 px minimum targets are required.
- Empty states explain what will happen next and offer the primary action.
- Never call a score “viral probability.” Use evidence, confidence, and uncertainty.
