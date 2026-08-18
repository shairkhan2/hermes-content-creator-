# The Fiction Ledger

Same schema and the same rules as `story-forge`'s loop ledger — one root question that
cannot be answered in a sentence, sub-questions that overlap so nothing is ever fully
resolved before the end, children resolving before their parents.

Read `story-forge`'s `references/loop-ledger.md` for the full schema, the nesting rules,
and the acts structure for anything past 15 beats. This file covers only what fiction
does differently.

## Fiction mode

Set it in the ledger, so the file carries its own truth rather than depending on how it
was invoked:

```json
{
  "mode": "fiction",
  "root_question": "...",
  "total_beats": 9
}
```

The embedded value wins over `--mode` on the command line.

## Deliberate ambiguity

`story-forge` errors on `orphan-question`: every question that opens must pay off. That
is right for research storytelling, which owes the listener an answer to everything it
raised.

Fiction does not owe that. "What was in the room?" left unanswered is horror working as
intended — the dread lives in the door, not behind it.

```json
{
  "id": "Q4",
  "text": "What was in the room?",
  "parent": "Q1",
  "opened_at": 3,
  "unresolved": true,
  "unresolved_reason": "Showing it collapses the dread. The story is about the door."
}
```

An unresolved question has no `pays_off_at`. The validator skips it in the nesting and
payoff checks, and treats it as open from `opened_at` through the end — which means it
satisfies the no-dead-beat rule for every beat after it opens.

## `unresolved_reason` is required

`unresolved: true` without a reason is an error, not a warning.

The validator cannot tell a deliberate ambiguity from a question the writer forgot to
close — they are byte-identical in the data. So it makes you write down which one it is.
Having to state the reason is usually enough to reveal that there isn't one.

## Use it once

At most twice. A story where nothing resolves is not ambiguous, it is unfinished.

The root question is the one to think hardest about. `mode: fiction` permits an
unresolved root, and the validator warns rather than errors — but read the warning:

> root Q1 never resolves. Ambiguity is a legitimate ending, but the story still has to
> land something in the final beat or it just stops.

An ambiguous *answer* is not the same as no answer. "The house was never haunted" and
"we never learn what it was" are both endings. "The story stops" is not.

## The ending problem

The commonest structural failure in horror is a final beat that explains.

The root question resolving is not the same as the ghost being explained. A story can
answer "why did she stay?" completely while never answering "what was in the room" —
and that is usually the strongest shape available, because the human question lands and
the supernatural one does not have to.

When designing the three candidate ledgers, check what each one's final beat actually
does. If it delivers an explanation of the supernatural, try the version where it
delivers an answer about the person instead.
