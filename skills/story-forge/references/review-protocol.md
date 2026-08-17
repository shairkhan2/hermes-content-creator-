# Review Protocol

Four auditors, each its own `delegate_task`, none sharing context with the writer or
with each other. Any one can reject. Unanimity to advance.

## Why four and not one

A single generalist reviewer hedges across concerns and approves the average. Asked to
weigh facts, structure, prose, and engagement at once, it produces a middling verdict
on all four and a decisive verdict on none.

Specialists reject on their own axis without weighing it against the others. The fact
auditor does not care that the prose is beautiful. The cold reader does not care that
the citations are perfect. That is the point.

## Why they must be separate agents

An auditor that watched the writer reason will defend the writer's choices. It has the
justification in context, so the weak line reads as intentional. Running the review in
the writing context turns the whole protocol into theatre.

Every auditor gets a fresh `delegate_task` and receives only its inputs — never the
writer's reasoning, never another auditor's verdict.

## The four

### Fact auditor

**Sees:** the draft, the research pack.
**Does not see:** the ledger, the other beats, the other drafts.

Walks every sentence and asks: is this an assertion about the world? If yes, which
claim ID covers it, and does the claim actually say this?

Rejects on:
- An assertion with no claim ID
- A claim ID that does not support what the sentence says
- A sentence that overstates its source — the pack says "linked to", the draft says "caused"
- A `low` confidence claim stated as settled fact
- A number, date, or name that drifted from the pack

### Structure auditor

**Sees:** the draft, `ledger.json`, the beat's assigned job, the list of questions open
at this point.
**Does not see:** the research pack, the other drafts.

Rejects on:
- The beat does not do the job the ledger assigns it
- A question the ledger says closes here does not actually resolve in the prose
- A question the ledger says opens here is not actually planted
- The beat resolves something early, leaving the listener with nothing
- The beat introduces a question that is not in the ledger

That last one matters. A writer inventing loops off-ledger breaks the validated
structure, and `check_ledger.py` cannot see it because it only reads the ledger.

### Prose auditor

**Sees:** the draft, `references/prose-rules.md`, the linter output.
**Does not see:** the pack, the ledger.

Starts where the linter stops. The linter catches banned constructions; the prose
auditor catches everything a regex cannot.

Rejects on:
- Restatement — the same beat delivered twice in different words
- Abstraction where a concrete image was available
- Uniform sentence rhythm the linter's stdev check did not quite catch
- Verbs doing no work: "is", "was", "has", "makes" carrying whole sentences
- A sentence that only exists to transition
- Anything that reads as written rather than spoken

### Cold reader

**Sees:** the draft, and the approved text of previous beats. Nothing else.
**Does not see:** the ledger, the pack, the beat's job, the word budget.

Reads once, at speed, the way a listener hears it. Does not analyse.

Reports:
- The exact line where attention first dropped, or "did not drop"
- What it expected to happen next at the end of the beat
- Anything it did not understand on one pass
- Whether it wants to keep going

Rejects when attention drops before the end of the beat, or when it cannot say what
question is still open.

The cold reader is the only auditor measuring the thing that actually matters. The
other three measure proxies for it.

## Verdict schema

Every auditor writes `reviews/beat-<nn>-<draft>-<auditor>.json`:

```json
{
  "beat": 3,
  "draft": "a",
  "auditor": "prose",
  "verdict": "reject",
  "scores": {
    "accuracy": null,
    "structure": null,
    "prose": 4,
    "engagement": null
  },
  "faults": [
    {
      "severity": "blocking",
      "excerpt": "The situation was complicated and difficult to resolve.",
      "problem": "Two abstract adjectives carrying the sentence. No image.",
      "fix": "Name what was complicated. The dredgers, the tide, the angle."
    }
  ],
  "weakest_element": "The closing sentence transitions without earning it.",
  "notes": ""
}
```

- `verdict` — `approve` or `reject`
- `scores` — 1–10 on the auditor's own axis; `null` for axes it does not judge
- `faults` — `blocking` faults force a reject; `minor` faults are recorded and carried
  forward but do not block
- `weakest_element` — **required even on approve**

## No silent approvals

An auditor returning `approve` with an empty `faults` array and an empty
`weakest_element` has not done the work. Re-run it once, explicitly requiring the
weakest element it can find.

If it comes back empty a second time, treat it as an abstention and count it as a
rejection. An auditor that cannot find the weakest line in a draft is not reviewing.

## Scoring and best-of-three

All three drafts are written and audited. Approval is the entry fee, not the finish
line — the first draft to clear the bar is just the first one that cleared it.

Composite score, equally weighted across the four axes:

```
score = (accuracy + structure + prose + engagement) / 4
```

Ties break on `engagement` — the cold reader's axis — because that is the one measuring
the real outcome.

Only drafts with four approvals are eligible. Score every eligible draft and take the
highest.

## Rounds and the escape valve

Up to three rounds per beat.

Each round hands the next writer the accumulated fault list from every prior round.
A fault repeated from a previous round scores double against the draft, because a
writer that has been told once and repeats it is not converging.

After round three, if nothing has four approvals: take the highest composite score,
write it to `beats/beat-<nn>.md`, and record the unresolved blocking faults in
`reviews/beat-<nn>-accepted-with-faults.json`. Surface them to the user at handoff.

This valve is not a quality compromise, it is a deadlock breaker. A pipeline with a
strict reviewer and no exit produces nothing at all, which is worse than producing
something whose flaws are written down.

If a beat needs the valve twice across one story, the fault is upstream — a thin
research pack or a ledger asking a beat to do something the material cannot support.
Go back rather than grinding.

## Full-pass review

Every beat passing individually does not mean the story works. Beat 7 can contradict
beat 2 while both pass locally, because no beat-level auditor sees both.

The final pass runs four checks with standing to send any beat back to step 5:

| Check | Looks for |
|---|---|
| Continuity | Contradictions, facts stated twice, phrasings reused across beats |
| Ledger closure | Re-run `check_ledger.py`; confirm the prose pays off each question where the ledger claims it does |
| Read-aloud | Sentences that work on the page and collapse when spoken |
| Cold reader, full length | One uninterrupted read, every drop-off point marked |

The full-length cold reader must be a **new** agent. The one that read beat 3 in
isolation has been contaminated by knowing how beat 3 resolved.

Verdict goes to `reviews/final-verdict.json` in the same schema, with `beat: null`.
