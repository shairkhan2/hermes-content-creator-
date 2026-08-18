# The Shot List

The shot list is where narration timing becomes visual structure. It is generated, not
written by hand, because it has to tile the audio exactly.

## Clauses in, shots out

TTS marks the narration at clause granularity — far finer than any shot needs. That is
deliberate: fine marks give the merger real boundaries to choose from, and choosing is
cheaper than splitting.

`build_shotlist.py` then merges consecutive clauses into the longest run that still fits
under the ceiling, never crossing a beat boundary.

```
b03c01  0.0 - 2.4  ┐
b03c02  2.4 - 5.1  ├─ s0012   0.0 - 7.6   (three clauses, 7.6s, under the ceiling)
b03c03  5.1 - 7.6  ┘
b03c04  7.6 - 9.9  ── s0013   7.6 - 9.9   (adding this would have exceeded 8s)
```

## The 8-second ceiling

Veo 3.1 renders at most 8 seconds per call. This is an API limit, not a style choice, so
`over-ceiling` is an error rather than a warning — an over-length shot cannot be
rendered at all.

The ceiling turns out to be roughly the right shot length anyway. Few shots in edited
video run longer, and chaining removes the need for any single clip to.

### Forced splits

A single clause longer than 8 seconds cannot be merged down. The builder splits it into
equal parts and sets `forced_split: true`.

The audio is never touched — only the visual is cut, mid-sentence. Flagged because the
boundary was forced by the ceiling rather than chosen for meaning, and those are the
cuts most likely to look wrong. Check them.

Frequent forced splits mean the narration has very long unbroken clauses. The real fix
is upstream: mark more finely during TTS.

## Chaining and cutting

**Within a beat, shots chain.** Shot N's end frame *is* shot N+1's start frame — the
same file, not a similar image. Continuity is structural rather than prompted, and drift
cannot accumulate because there is nothing to drift between.

**At a beat boundary, hard cut.** New frame series, `chain_from: null`,
`transition: "cut"`.

Beats are where the story's question chain turns, so the edit lands on the structure
instead of fighting it. A viewer watching muted should be able to feel the beats.

```
beat 3:  f03_00 ──s0012──► f03_01 ──s0013──► f03_02 ──s0014──► f03_03
                                                                  ╳  cut
beat 4:  f04_00 ──s0015──► f04_01 ──s0016──► f04_02
```

A beat of *m* shots needs *m+1* frames. The interior ones are **hinges**, belonging to
two shots at once.

## What the validator enforces

`check_shotlist.py`. Errors block the render; warnings want a reason.

| Code | Severity | Meaning |
|---|---|---|
| `over-ceiling` | error | Shot longer than the API can render |
| `timeline-gap` | error | Narration with no shot covering it |
| `timeline-overlap` | error | Two shots covering the same audio |
| `timeline-short` | error | Shots end before the narration does |
| `broken-chain` | error | Mid-beat shot that does not chain — a cut inside a beat |
| `chain-across-beats` | error | Chaining over a boundary that should cut |
| `chain-frame-mismatch` | error | Chained shots not sharing a frame |
| `chain-mismatch` | error | `chain_from` pointing at the wrong shot |
| `degenerate-shot` | error | Start and end frame identical — nothing to interpolate |
| `unknown-frame` | error | Reference to a frame that does not exist |
| `frame-overused` | error | A frame used by more than two shots |
| `bad-motion` | error | Motion outside camera/subject/reveal/hold |
| `no-motion` | warn* | Undeclared motion (*error under `--require-motion`) |
| `no-prompt` | error† | Unfilled prompt (†only under `--require-prompts`) |
| `flicker` | warn | Shot below the minimum — reads as a flash |
| `orphan-frame` | warn | Frame generated but never used |
| `large-render` | warn | Over 150 clips; confirm scale and budget first |

Run it twice: once bare after building, once with `--require-prompts --require-motion`
after prompts are written. The first proves the structure; the second proves it is ready
to render.

## Do not hand-edit timings

Shot times tile the narration exactly. Changing one desyncs everything after it, and the
validator will report a gap or an overlap you then have to chase.

If shots are wrong, fix the input and rebuild. Nothing in the shot list is authored by
hand except prompts and motion.
