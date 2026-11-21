# Moment Selection and Short Assembly

## Product decision

TrendClip must not present an algorithmic peak as if it were automatically a good Short. Loudness, motion, replay activity, or an exciting word can identify an interesting instant while missing the setup, payoff, or context that makes it understandable.

The pipeline therefore separates three decisions:

1. **Signal detection** — where something potentially interesting happens.
2. **Story-beat classification** — whether a segment behaves like a hook, setup, escalation, payoff, reaction, explanation, or ending.
3. **Short assembly** — which compatible beats form a coherent, self-contained video.

## Default user experience

The recommended default is **Auto-build best Short**. TrendClip produces three drafts:

- **Top pick** — strongest eligible candidate according to completeness and observed energy; the deterministic scorer does not claim full story understanding.
- **High energy** — faster action/reaction cut with minimal setup.
- **Quick hit** — shortest self-contained moment suitable for a meme or rapid highlight.

The user can preview and download a draft without selecting timestamps. Manual controls remain available through two alternatives:

- **Single highlight** — one continuous source range, with adjustable start/end handles.
- **Build a montage** — select several story beats; TrendClip orders and trims them rather than concatenating them blindly.

## What the user sees

Each candidate beat needs enough evidence for a non-editor to judge it:

- Representative thumbnail or short hover preview.
- Plain-language label such as Hook, Setup, Action, Payoff, or Reaction.
- Transcript excerpt with the strongest sentence emphasized.
- Start time and duration.
- A one-sentence explanation: “Large motion change + excited reaction + replay peak.”
- Component score bars, not one unexplained virality number.
- Confidence and warnings such as “payoff missing,” “starts mid-sentence,” or “visual action but little context.”
- Buttons to preview with 3–5 seconds of surrounding context.

The interface should initially show the three assembled drafts. Candidate beats and technical scores belong in an expandable **Why these moments?** panel.

## Assembly model

A complete 15–35 second Short normally contains:

| Beat | Typical length | Purpose |
|---|---:|---|
| Hook | 1–3 s | Creates a clear question, surprise, or promise. |
| Setup | 2–7 s | Supplies the minimum context needed to understand the event. |
| Action or escalation | 5–15 s | Shows the meaningful gameplay or reaction. |
| Payoff | 3–10 s | Delivers the result, reveal, failure, joke, or insight. |
| Exit or loop | 0–2 s | Ends cleanly or returns naturally to the opening. |

Not every Short needs five separate cuts. A single continuous segment can satisfy several roles. Non-contiguous segments should be combined only when they share the same event, participants, and narrative context.

## Default no-LLM analysis

The free baseline remains deterministic and local:

- Sentence and pause boundaries from Faster Whisper and voice activity.
- Loudness changes and reaction peaks.
- Motion intensity, shot changes, and optical-flow changes.
- YouTube replay data when available.
- Speech emphasis and gaming/reaction phrases.
- Repeated or unusual on-screen changes.
- Beginning/end completeness: avoid entering mid-sentence or leaving before the result.
- Diversity: do not return several candidates from the same near-identical event.

These signals produce candidate beats and explainable component scores. They cannot understand every joke, secret, strategy, or gameplay event.

## Optional semantic analyzers

An optional local vision/language model, Ollama endpoint, Codex adapter, or other provider can improve:

- Semantic hook and payoff detection.
- Whether two distant beats describe the same event.
- Gameplay-event labels.
- Context completeness.
- Hook and metadata writing.

Optional analyzers must implement a versioned interface and return structured beat labels, relationships, confidence, and rationale. The core workflow must remain usable without them.

## Quality gates

An automatically assembled draft is rejected or downgraded when:

- It begins or ends in the middle of a spoken clause.
- The promised hook has no visible or spoken payoff.
- Selected beats describe unrelated events.
- The same event is repeated without purpose.
- Captions miss meaningful speech.
- A cut hides the relevant subject or gameplay area.
- The result contains long dead air, frozen visuals, or an abrupt audio discontinuity.
- The Short cannot be understood without watching substantial omitted context.

The deterministic baseline requires at least 7.5/10 editorial quality, clean opening and ending boundaries, evidence of a hook, payoff, or relevant content event, and no detected sensitive-language flag. If no candidate passes, Studio reports that no strong complete moment was found and does not promote the least-weak candidate as the Top pick. These checks are deliberately conservative and remain a pre-review aid—not semantic proof that a clip will go viral.

## Implementation sequence

1. Segment transcripts at sentence/pause boundaries and video at shot changes.
2. Convert current score peaks into labeled candidate beats with context windows.
3. Add completeness, payoff, continuity, and diversity scores.
4. Build three deterministic draft recipes.
5. Add thumbnail strips, transcript excerpts, surrounding-context preview, and score explanations.
6. Add manual range adjustment and montage selection.
7. Add optional semantic analyzer adapters after the deterministic workflow is stable.

## Success criterion

A user should be able to choose from up to three understandable assembled drafts without reading raw timestamps—or receive an honest no-suitable-moment result. If they open the evidence panel, they should be able to explain what TrendClip detected, why the beats belong together, and which uncertainty remains.
