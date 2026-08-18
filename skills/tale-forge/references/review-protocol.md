# Review Protocol

Four auditors, each its own `delegate_task`, none sharing context with the writer or
each other. Any one can reject. Unanimity to advance. Three drafts of every beat, scored
on the same rubric, best of three.

The structure, the verdict schema, the no-silent-approvals rule, the fault propagation,
and the three-round escape valve are identical to `story-forge`'s
`references/review-protocol.md`. Read that first. This file covers the differences.

## Why they must still be separate agents

Unchanged, and worth repeating because fiction makes it tempting to cheat. An auditor
that watched the writer reason has the justification in context, so the weak line reads
as intentional — and in fiction almost anything can be defended as intentional. Separate
agents, every time, or the review is theatre.

## Canon auditor (replaces the fact auditor)

**Sees:** the draft, `canon.json`.
**Does not see:** the ledger, the other beats, the other drafts.

Walks every named person, place, object, and rule in the draft and checks it against the
canon.

Rejects on:

- A named entity that is not in `canon.json`
- A detail contradicting an established fact — age, appearance, timeline, geography
- **The supernatural breaking its own rules.** The most important check here. If R001
  says it only manifests in silence and this beat has it appear during a storm, that is
  a reject regardless of how good the scare is
- A rule quietly widened — the entity doing something not forbidden but never
  established either, which is how limits erode a beat at a time

That last one is the subtle failure. Rules do not usually break; they stretch. Each beat
takes slightly more license than the last, no single beat looks wrong, and by act three
the threat can do anything. The auditor's job is to catch the stretch at the beat where
it starts.

Score `canon` 1–10. Leave the other axes null.

## Structure auditor

Unchanged from `story-forge`, with one addition: it also verifies that anything the
ledger marks `unresolved` is genuinely *left* open in the prose — not accidentally
answered, and not quietly forgotten.

A beat that resolves a question the ledger says stays open is a reject. So is a beat
that treats a deliberately open question as if it had never been raised.

## Prose auditor

Same brief as `story-forge`, plus fiction's two hard fails, which the linter has already
flagged mechanically:

- **Told emotion** — the feeling named rather than caused
- **Genre cliché** — stock gestures instead of the specific detail

The auditor starts where the linter stops. It should not re-report those; it catches
what a regex cannot:

- Emotion told in a way no pattern matches — a paragraph that explains a character's
  state instead of showing it
- The scare arriving without setup, or setup that never pays
- POV slips: information delivered that the viewpoint character could not have
- Escalating vocabulary doing the work plain language should do
- A description that gives the reader the shape of the thing when withholding it was
  stronger

## Cold reader

The most important auditor in fiction, and the one to be most careful not to
contaminate.

**Sees:** the draft, and the approved text of previous beats. **Nothing else** — no
canon, no ledger, no beat job, no word budget.

For fiction it reports:

- The exact line where attention first dropped, or "did not drop"
- What it expected to happen next
- **Whether anything unsettled it, and precisely where** — the line, not the paragraph
- Anything it did not follow on one pass
- Whether it wants to keep going

Rejects when attention dropped before the end, when it cannot name an open question, or
when a beat meant to unsettle produced nothing.

That last one has no proxy. The canon auditor cannot tell you the scare failed. The
linter certainly cannot. Only a reader encountering it cold can, and only once — which
is why a fresh agent is needed for the full-length pass at the end. The one that read
beat three in isolation now knows how beat three resolved and can never read it cold
again.

## Scoring

```
score = (canon + structure + prose + engagement) / 4
```

Ties break on `engagement`. In fiction that is not a tiebreaker of convenience — it is
the axis measuring whether the story works at all, while the other three measure whether
it is well made. A well-made story nobody wants to finish has failed.
