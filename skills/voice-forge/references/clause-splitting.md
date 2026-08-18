# Clause Splitting

`shot-forge` needs boundaries finer than sentences to merge back up into shots under
Veo's 8-second ceiling. `split_clauses.py` produces those boundaries once, here, rather
than leaving either the TTS call or the shot builder to guess at sentence structure.

## The algorithm

1. Read each beat's text file (from `handoff.json`'s `beats[].text_file`).
2. Strip markdown structure and `[Cxxx]` citation markers — narration is never voiced
   with a citation bracket in it.
3. Split into sentences on `. ! ?` boundaries.
4. A sentence longer than 12 words is a candidate for further splitting at internal
   commas, semicolons, or em-dashes.
5. A sub-split piece shorter than 3 words folds back into its neighbour — "and" is not
   a clause on its own.

```
"The wind came across the beam at forty knots, on a hull stacked nine
containers high, and the sand shifted under the bow."
```

is 12+ words and splits at its commas into three clauses; a short six-word sentence
elsewhere in the same beat stays whole.

## The comma-in-a-number guard

Splitting only happens at a comma followed by a **letter**, never a digit. Without this,
"3,000 metres" reads as a clause boundary in the middle of a number, which is wrong both
for TTS pacing and for the shot list built on top of it.

## Numbering

`b<NN>c<NN>` — beat number, then clause number restarting at 1 within each beat. This is
the mark name both backends key off, directly (Vertex) or via offset (ElevenLabs), and
it's what `shot-forge`'s `build_shotlist.py` parses back out.

## What gets emitted

Four outputs from one pass over the clauses, so they cannot disagree with each other:

| File | For | Contents |
|---|---|---|
| `clauses.json` | both | The clause list itself — beat, clause, mark, text |
| `ssml.xml` | Vertex | `<speak>` with a `<mark>` before each clause |
| `plain.txt` | ElevenLabs | The exact text to send — no marks, since v3 has none |
| `offsets.json` | ElevenLabs | Each clause's character offset within `plain.txt` |

`plain.txt` and `offsets.json` come from the same rendering loop
(`render_plain` in `split_clauses.py`) specifically so the offsets are guaranteed
correct against that exact string. If `plain.txt` is edited after generation, the
offsets no longer describe it — regenerate both together, never one alone.

## Tuning the thresholds

`SUB_SPLIT_WORD_THRESHOLD` (12) and `MIN_CLAUSE_WORDS` (3) are the two knobs. Raising the
threshold produces fewer, longer clauses — coarser shot boundaries downstream. Lowering
`MIN_CLAUSE_WORDS` allows shorter fragments, which read naturally in dialogue-heavy
prose but produce more forced splits later if a clause runs long anyway.

Change them only with a reason tied to how the output sounds or cuts, not to make a
particular script's test pass.
