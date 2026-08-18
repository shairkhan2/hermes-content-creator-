---
name: tale-forge
description: Write original fiction with a canon lock and staged review.
version: 0.1.0
author: shairkhan2, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [fiction, story, horror, ghost-story, narrative, creative-writing, screenplay]
    related_skills: [story-forge]
    requires_toolsets: [terminal, file]
    requires_tools: [delegate_task]
    config:
      - key: tale_forge.words_per_minute
        description: "Narration pace used to convert a duration target into a word budget"
        default: 150
        prompt: "Narration words per minute (150 is a normal speaking pace)"
      - key: tale_forge.workspace
        description: "Directory where story projects are created"
        default: "~/tale-forge"
        prompt: "Where should story projects be written?"
---

# Tale Forge

Writes original fiction — ghost stories, folk horror, thrillers, anything invented — to
a narration-ready script. Same machinery as `story-forge`: beats with hard word caps,
three drafts of everything, four independent auditors, best of three. What changes is
what the writer is held to.

`story-forge` locks the writer to a set of sourced facts. There are no facts here, so
the lock becomes a **canon**: everything the story has established about its own world.
The failure it prevents is not hallucination but drift — the ghost's rules changing in
act three, a character's name shifting, a house that had two floors growing a third.

## When to Use

- The user wants a made-up story: ghost story, horror, thriller, fable, sci-fi.
- The user names a genre and a length and wants something written.
- The user has a premise and wants it built out properly rather than improvised.

Don't use for:

- Anything factual. Research storytelling is `story-forge`, and its sourcing discipline
  is the whole point — do not write real events as fiction.
- Continuing someone else's copyrighted world with its characters.
- A single paragraph or a writing prompt. The review machinery costs more than the output.
- Producing the video. That is `shot-forge`.

## Prerequisites

- `delegate_task` for the auditors. **Auditors must be separate agents.** An auditor
  that watched the writer reason will defend the writer's choices.
- Python 3.9+ for the two validators. No third-party packages.

## What changes from story-forge

| | `story-forge` | `tale-forge` |
|---|---|---|
| The lock | Research pack — sourced claims | Canon — invented facts, once established |
| The risk | Stating something untrue | Contradicting yourself |
| First auditor | Fact auditor, against the pack | **Canon auditor**, against the bible |
| Unanswered questions | Always an error | Allowed, if declared and justified |
| Linter | Citations, unfalsifiable attribution | **Told emotion**, genre cliche |
| Research step | Web search, independent verification | Premise development, canon design |

Everything else is identical: the loop ledger, beat budgets, three drafts, four
auditors, unanimity, best of three, the escape valve.

## The Rules

1. **No word count reaches the writer.** One beat, its job, its cap. Never a duration.
2. **Canon is a closed set.** A named person, place, object, or rule must be in
   `canon.json` before prose can use it. Inventing on the fly is how act three
   contradicts act one.
3. **Show, never name the feeling.** "She was terrified" is a hard fail. A reader told
   they are frightened stops being frightened.
4. **Three drafts of everything, always.** Approval is the entry fee, not the finish line.
5. **Unanimity to advance.** Four auditors, any one can reject.
6. **No silent approvals.** Name the weakest thing even when approving.
7. **An unanswered question must be declared.** Ambiguity is a decision, marked in the
   ledger with a reason — never a question the writer forgot to close.

## Story Shape

Identical to `story-forge`: a chain of nested, overlapping questions with one root that
cannot be answered in a sentence. See `references/loop-ledger.md` there, or the copy of
the schema in `references/fiction-ledger.md` here.

One difference, and it matters for horror.

`story-forge` errors on any question that never pays off. Fiction may leave one open on
purpose — "what was in the room?" unanswered is the genre working, not a defect. So the
ledger runs in fiction mode:

```json
{
  "mode": "fiction",
  "questions": [
    {
      "id": "Q4",
      "text": "What was in the room?",
      "parent": "Q1",
      "opened_at": 3,
      "unresolved": true,
      "unresolved_reason": "Showing it collapses the dread. The story is about the door, not what is behind it."
    }
  ]
}
```

`unresolved` without `unresolved_reason` is an error. The distinction the validator
enforces is between a decision and an oversight, and it cannot read your mind — so it
makes you write the reason down.

Use it **once**, at most twice. A story where nothing resolves is not ambiguous, it is
unfinished.

## Procedure

### 1. Intake

Record in `brief.md`: genre, length, audience, tone, point of view, tense, and any
premise the user supplied. Ask only what you cannot infer.

Convert duration to beats with the table in `story-forge`'s SKILL.md — same arithmetic,
same acts-past-15-beats rule. The writer never sees it.

### 2. Build the canon

The fiction equivalent of the research pack, and the step most likely to be skipped.

Write `canon.json` before any prose: characters, places, objects, and — most
importantly for supernatural fiction — **the rules**. What the ghost can and cannot do.
What it wants. What it costs to see it. Under what condition it appears.

```json
{
  "premise": "...",
  "entities": [
    {"id": "E001", "kind": "character", "name": "Sarah Vance",
     "facts": ["37", "sound engineer", "moved in three weeks ago"]},
    {"id": "E002", "kind": "place", "name": "the fourth stair",
     "facts": ["creaks under any weight", "stopped creaking on the third night"]}
  ],
  "rules": [
    {"id": "R001", "rule": "It only manifests in absolute silence.",
     "consequence": "Any noise is safety, which makes quiet rooms unbearable."}
  ]
}
```

Rules are the load-bearing part. Horror fails when the supernatural can do anything,
because a threat with no limits has no tension — the audience cannot tell what counts
as a near miss. Write the limits down and hold to them.

Detail: `references/canon.md`.

### 3. Design the loop ledger — three candidates

Three genuinely different structures, not three phrasings. Different root question,
different entry point, different order of revelation.

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <project>/ledger-a.json --mode fiction", timeout=60)
```

Structure auditor picks the winner. Copy it to `ledger.json`.

### 4. Write each beat — three drafts, four auditors

For beat *n*: three drafts, each its own `delegate_task`, each given the beat's job, its
word cap, the open questions, the full canon, and the approved text of previous beats.
Never the total length.

Lint all three:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <project>/beats/beat-03-a.md --mode fiction --budget 95 --json", timeout=60)
```

Then four auditors, separate agents, no shared context:

| Auditor | Checks | Rejects when |
|---|---|---|
| Canon auditor | Every name, place, object, rule against `canon.json` | Something contradicts canon, or a new entity appears without being added |
| Structure auditor | The beat against the ledger | The beat fails its job, closes a loop early, or opens one not in the ledger |
| Prose auditor | Word choice, rhythm, told emotion, cliche | Feeling named rather than caused, genre furniture, restatement |
| Cold reader | Reads once, no canon, no outline | Names the exact line where attention dropped, or where they lost the thread |

Four approvals to pass. Score all passing drafts and take the highest. Up to three
rounds, faults propagating forward, then the escape valve.

Detail: `references/review-protocol.md`.

### 5. Assemble and review the whole

Concatenate to `story.md`. Then a full pass with standing to send any beat back:

- **Canon continuity** — contradictions across beats that no single-beat auditor could see
- **Rule integrity** — does the supernatural obey its own rules end to end?
- **Ledger closure** — re-run `check_ledger.py --mode fiction`; confirm the prose pays
  off what the ledger says it does, and that anything left open was declared
- **Cold reader, full length** — a new agent, one uninterrupted read

### 6. Handoff

Write `story-clean.md` and `handoff.json` in the same shape `story-forge` emits, so
`shot-forge` can consume it unchanged.

```
[[as_document]]
```

## Quick Reference

```
python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py ledger.json --mode fiction
python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py ledger.json --mode fiction --json
python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py draft.md --mode fiction --budget 95
python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py draft.md --mode fiction --json --strict
```

Both exit `0` clean, `1` on findings, `2` on bad input. `mode` may also be set inside
the ledger file, which then wins over the flag.

## Pitfalls

- **Skipping the canon.** It feels like overhead on a short story and then act three
  contradicts act one. The canon auditor has nothing to check against without it.
- **A threat with no rules.** If the ghost can do anything, nothing is a near miss and
  there is no tension. Write the limits before the scares.
- **Naming the feeling.** The single most common failure in horror prose, and the
  linter fails it hard. Cause the feeling with a detail instead.
- **Genre furniture.** Chills down spines, pounding hearts, deafening silence. Each one
  is a writer reaching for the stock gesture instead of the specific detail.
- **Over-using `unresolved`.** Once is haunting. Three times is an unfinished draft with
  a justification attached.
- **Explaining the ending.** The impulse to clarify in the last beat is the impulse that
  kills the story. The root question resolving is not the same as the ghost being explained.
- **Auditors sharing the writer's context.** Then the review is theatre. Separate
  `delegate_task` every time.

## Verification

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <project>/ledger.json --mode fiction", timeout=60)
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <project>/story.md --mode fiction --budget <total> --json", timeout=120)
```

- Both exit `0`.
- Every entity and rule the prose uses appears in `canon.json`.
- `reviews/` holds a verdict for every beat × draft × auditor.
- Anything left unresolved is marked with a reason.
- Read it aloud. If you can stop before the last beat without needing to know what
  happens, the ledger failed, not the prose.

## References

| File | Contents |
|---|---|
| `references/canon.md` | Entities, rules, why limits create tension |
| `references/fiction-ledger.md` | Ledger schema, fiction mode, deliberate ambiguity |
| `references/fiction-prose.md` | Told emotion, genre cliche, what horror prose does |
| `references/review-protocol.md` | The four auditors, prompts, rubric, verdict schema |
