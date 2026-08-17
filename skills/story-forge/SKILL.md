---
name: story-forge
description: Research topics and write fact-locked, reviewed stories.
version: 0.1.0
author: shairkhan2, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [writing, research, storytelling, script, narrative, fact-checking, content]
    related_skills: []
    requires_toolsets: [terminal, file, web]
    requires_tools: [web_search, web_extract, delegate_task]
    config:
      - key: story_forge.words_per_minute
        description: "Narration pace used to convert a duration target into a word budget"
        default: 150
        prompt: "Narration words per minute (150 is a normal speaking pace)"
      - key: story_forge.workspace
        description: "Directory where story projects are created"
        default: "~/story-forge"
        prompt: "Where should story projects be written?"
---

# Story Forge

Turns a topic into a narration-ready story script through a research phase that
produces a closed set of sourced claims, and a writing phase where every beat is
drafted three times and cleared by four independent auditors before the next beat
begins. It does not generate video, audio, or images — it ends at an approved
script and a handoff manifest.

The whole design exists to defeat one failure: asked for "a 5-minute story," a
model agrees, targets a word count, and pads to length. Padding to length **is**
the slop. So this skill never gives the writer a duration. It gives beats, each
with a job and a hard cap, and a research pack the writer may not step outside of.

## When to Use

- The user asks for a story, script, narration, or explainer on a topic.
- The user wants researched content where the facts have to actually hold up.
- The user says a previous draft felt generic, padded, or AI-written.
- The user gives a duration ("5 minutes", "90 seconds") for spoken content.

Don't use for:

- Fiction with no factual spine — the research pack has nothing to lock onto.
- One-line copy, titles, or captions. The review machinery costs more than the output.
- Editing a draft the user wrote themselves. Use `patch` directly.
- Producing the video/audio. This skill stops at the script.

## Prerequisites

- `web_search` and `web_extract` for the research phase.
- `delegate_task` for the auditors. **Auditors must be separate agents.** An auditor
  that watched the writer reason will defend the writer's choices.
- Python 3.9+ on PATH for the two validator scripts. No third-party packages.

Verify with:

```
terminal(command="python3 --version", timeout=30)
```

## How to Run

Create the project directory, then work through the procedure in order. Every stage
writes a file; nothing is held in conversation memory, because a later auditor has to
be able to read the artifact cold.

```
terminal(command="mkdir -p <workspace>/<slug>/{research,ledger,beats,reviews}", timeout=30)
```

Validators, invoked throughout:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <project>/ledger/ledger.json", timeout=60)
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <project>/beats/beat-03-a.md --pack <project>/research/pack.json --budget 95", timeout=60)
```

## The Rules

These are not style preferences. Each one is enforced by a script or an auditor, and
a violation blocks the stage.

1. **No word count reaches the writer.** The writer is given one beat, that beat's
   job, and that beat's word cap. It never learns the total target.
2. **The research pack is a closed set.** Every factual claim in the script must
   carry a claim ID from the pack. A statement of fact without an ID is a hard fail,
   whether or not it happens to be true.
3. **Three drafts of everything, always.** Not three-on-failure. Approval is the
   entry fee, not the finish line — the first draft that clears the bar is just the
   first one that cleared it.
4. **Unanimity to advance.** Four auditors, any one can reject. No majority vote.
5. **No silent approvals.** An auditor must name the weakest thing it found even when
   approving. "Approved, no notes" is treated as a non-response and re-run once.
6. **Faults propagate forward.** Draft 2 is written with draft 1's fault list in hand.
   A repeated fault is scored double.
7. **The ledger is auditable before prose exists.** A broken question-chain cannot be
   rescued by good sentences, so it is designed, validated, and reviewed first.

## Story Shape

The story is a chain of nested questions, never a list of facts.

Beat 1 opens with a question. The story unfolds it — and before it closes, a new
question is planted on top. At no point in the middle of the story is everything
resolved, because a listener with nothing unresolved leaves.

Underneath sits one **root question** that the whole piece answers. The root cannot
be answered directly — if it could, there would be no story, just a sentence. So it
is decomposed into sub-questions that can be answered, each one's answer setting up
the next one's premise. The root closes last, in the final beat, and closes alone.

This is tracked in `ledger/ledger.json` as a **loop ledger** — every question with
where it opens, where it pays off, and which question it hangs from. That turns
"do the questions connect?" from a matter of taste into three checks a script can run:

- No beat except the last has zero open sub-questions.
- Every question that opens, pays off. No orphans.
- Children nest inside parents — a child cannot outlive the question that raised it.

Full schema and worked examples: `references/loop-ledger.md`.

## Procedure

### 1. Intake

Ask only what you cannot infer. Record in `research/brief.md`: topic, audience,
duration target, tone, and anything the user says is off-limits or must be included.

Convert duration to structure — the writer never sees this arithmetic:

| Target | Words @150wpm | Beats | Words/beat |
|---|---|---|---|
| 60 s | 150 | 3 | 40–60 |
| 90 s | 225 | 4 | 45–70 |
| 3 min | 450 | 6 | 60–90 |
| 5 min | 750 | 9 | 70–110 |
| 10 min | 1500 | 14 | 90–130 |

Beats are deliberately not uniform. Beat 1 runs short; payoff beats run long.

Completion: `research/brief.md` exists and names a duration, an audience, and a tone.

### 2. Research → the pack

Run `web_search` broadly first, then `web_extract` on the sources worth reading in
full. Prefer primary sources — a paper, a filing, a transcript, a dataset — over
articles describing them.

Write every usable fact into `research/pack.json` as a claim with a stable ID:

```json
{
  "topic": "...",
  "claims": [
    {
      "id": "C001",
      "text": "The Ever Given was refloated on 29 March 2021, six days after grounding.",
      "sources": ["https://..."],
      "confidence": "high",
      "verified": false
    }
  ]
}
```

`confidence` is `high` (primary source, directly stated), `medium` (secondary source
or inference), or `low` (contested, single weak source). Anything you cannot source
does not enter the pack. It does not go in as `low` — it does not go in.

Aim for roughly 3× more claims than the story can hold. The writer choosing from an
abundant pack writes better than a writer stretching a thin one.

Completion: `research/pack.json` parses, and every claim has ≥1 source URL.

### 3. Verify the research independently

The pack stops the writer inventing facts. It cannot catch a fact that was already
wrong when gathered — and that is the more dangerous error, because everything
downstream will treat it as ground truth.

Delegate a fact-checker that does **not** see the original research session:

```
delegate_task(
  prompt="You are a fact-checker. For each claim in <project>/research/pack.json, "
         "search independently for corroboration. Do not use the URLs already listed "
         "as your starting point. For each claim output: id, verdict "
         "(confirmed|contested|refuted|unsourceable), and the sources you found. "
         "Read " + "${HERMES_SKILL_DIR}/references/research.md" + " for the standard.",
  ...
)
```

Apply the results: `confirmed` → `verified: true`. `contested` → keep, drop confidence
to `low`, and the writer must frame it as disputed. `refuted` or `unsourceable` →
delete the claim from the pack.

Completion: every claim has `verified: true` or a recorded downgrade/removal reason.

### 4. Design the loop ledger — three candidates

Write three *different* structural approaches to the same material, not three
variations of one. Different root questions, different entry points. Save as
`ledger/ledger-a.json`, `-b.json`, `-c.json`.

Validate each mechanically before any human-judgment review:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <project>/ledger/ledger-a.json", timeout=60)
```

Then delegate the **structure auditor** on all three (see `references/review-protocol.md`).
It scores each and picks one. Copy the winner to `ledger/ledger.json`.

If all three fail validation, the material may not support the requested length. Say
so to the user rather than padding — that is exactly the moment slop gets created.

Completion: `check_ledger.py` exits 0 on `ledger/ledger.json`, and a written rationale
for the pick sits in `reviews/ledger-verdict.json`.

### 5. Write each beat — three drafts, four auditors

For beat *n*, in order:

**5a. Write three drafts.** Each gets its own `delegate_task`. The writer prompt
contains: the beat's job from the ledger, its word cap, the questions open at that
point, the full research pack, and the approved text of all previous beats. It does
**not** contain the total word target, the other drafts, or the beats not yet written.

Save as `beats/beat-<nn>-a.md`, `-b.md`, `-c.md`. Cite claims inline as `[C012]`.

**5b. Lint all three.** Deterministic, no judgment involved:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <project>/beats/beat-03-a.md --pack <project>/research/pack.json --budget 95 --json", timeout=60)
```

A clean lint does not skip the auditors. It means the auditors start from a clean file.

**5c. Run all four auditors on all three drafts.** Separate `delegate_task` calls,
no shared context between them:

| Auditor | Checks | Rejects when |
|---|---|---|
| Fact auditor | Every sentence against the pack | A claim is uncited, miscited, or overstates its source |
| Structure auditor | The beat against the ledger | The beat fails its job, closes a loop early, or opens nothing |
| Prose auditor | Word choice, rhythm, redundancy | Filler, hedging, restatement, uniform sentence length |
| Cold reader | Reads once, no outline, no pack | Names the exact line where attention would drop |

Verdicts go to `reviews/beat-<nn>-<draft>-<auditor>.json` in the schema in
`references/review-protocol.md`. Every verdict lists faults, approving or not.

**5d. Advance.** A draft passes only with four approvals. Score all passing drafts on
the rubric and take the highest. Write it to `beats/beat-<nn>.md`.

**5e. If nothing passes,** rewrite — up to three rounds total. Each round hands the
next writer the accumulated fault list; a fault repeated from a prior round scores
double. After round three, take the highest scorer and record its unresolved faults
in `reviews/beat-<nn>-accepted-with-faults.json`. Ship it knowing what is wrong with
it, and tell the user at handoff. A pipeline with no escape valve deadlocks and
produces nothing, which is worse than producing something flagged.

Completion: `beats/beat-<nn>.md` exists and every auditor verdict is on disk.

### 6. Assemble and review the whole

Concatenate approved beats into `story.md`. Every beat passing on its own does not
mean the story works — beat 7 can quietly contradict beat 2 while both pass locally.

Run a full-pass review with standing to send any beat back to step 5:

- **Continuity** — contradictions, repeated facts, repeated phrasings across beats
- **Ledger closure** — re-run `check_ledger.py`, confirm the prose actually pays off
  each question where the ledger claims it does
- **Read-aloud** — sentences that work on the page and collapse when spoken
- **Cold reader, full length** — one uninterrupted read, marks every drop-off point

Completion: `story.md` exists and `reviews/final-verdict.json` records an approval.

### 7. Handoff

Strip the `[Cxxx]` citations from the narration text into `story-clean.md`, keeping
the cited version as the record. Write `handoff.json`:

```json
{
  "title": "...",
  "duration_target_s": 300,
  "word_count": 741,
  "beats": [{"n": 1, "words": 74, "text_file": "beats/beat-01.md"}],
  "root_question": "...",
  "unresolved_faults": [],
  "sources": ["https://..."]
}
```

Deliver by ending the response with the absolute path to `story-clean.md`, then:

```
[[as_document]]
```

## Quick Reference

```
python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <ledger.json>
python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <ledger.json> --json
python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <draft.md> --pack <pack.json> --budget 95
python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <draft.md> --pack <pack.json> --budget 95 --json
python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <draft.md> --budget 95 --no-claims
```

Both exit `0` clean, `1` on findings, `2` on bad input.

## Pitfalls

- **Auditors in the writer's context rubber-stamp.** Every auditor is its own
  `delegate_task`. If they share context, the review is theatre.
- **"Approved, no notes" is a non-response.** Re-run the auditor once, requiring a
  named weakest element. If it comes back empty again, treat as an abstention and
  count it as a rejection.
- **A thin pack causes slop downstream.** If the writer is stretching four facts
  across nine beats, the fault is in step 2, not step 5. Go back and research more.
- **The linter is objective, not smart.** It catches banned constructions and budget
  overruns. It cannot tell you the beat is boring. That is the cold reader's job, and
  neither substitutes for the other.
- **Don't let the writer see the duration.** If any writer prompt contains "5 minutes"
  or "750 words", the padding behaviour comes straight back.
- **Three different structures, not three phrasings.** If all three candidate ledgers
  share a root question, you ran one design and wrote it out three times.
- **Contested facts are an asset.** A claim marked contested, framed as contested, is
  more interesting than a smooth false certainty. Don't discard tension to sound clean.

## Verification

The pipeline worked if all of the following hold:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <project>/ledger/ledger.json", timeout=60)
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/lint_draft.py <project>/story.md --pack <project>/research/pack.json --budget <total> --json", timeout=120)
```

- Both exit `0`.
- `reviews/` holds a verdict file for every beat × draft × auditor. Missing files mean
  a stage was skipped.
- Every claim in `pack.json` referenced by the story has `verified: true`.
- Word count is within 10% of target — as an *outcome* of the beat budgets, never as
  something the writer aimed at.
- Read `story-clean.md` aloud end to end. If you can stop reading at any point before
  the last beat without wanting to know what happens next, the ledger failed, not the prose.

## References

| File | Contents |
|---|---|
| `references/loop-ledger.md` | Ledger schema, nesting rules, worked 9-beat example |
| `references/research.md` | Sourcing standard, claim IDs, the independent verification pass |
| `references/prose-rules.md` | Banned constructions, word choice, rhythm, the full slop list |
| `references/review-protocol.md` | The four auditors, prompts, rubric, verdict schema |
| `references/troubleshooting.md` | Deadlocks, thin packs, failure modes and their fixes |
