# hermes-content-creator

Hermes Agent skills for content creation. Currently one skill: **Story Forge**.

## Story Forge

Turns a topic into a narration-ready script through a research phase that produces a
closed set of sourced claims, and a writing phase where every beat is drafted three
times and cleared by four independent auditors before the next beat begins.

It stops at an approved script. It does not generate video, audio, or images — Hermes
already ships `video_generate`, `image_generate`, and `text_to_speech` for that.

### The problem it exists to solve

Ask a model for "a 5-minute story" and it agrees, targets a word count, and pads to
length. Padding to length **is** the slop.

So the writer is never told the duration. It gets one beat, that beat's job, and a hard
word cap. A beat that does its job in 60 words against a cap of 95 stops at 60.

### How it works

```
intake → research pack → independent fact verification
       → 3 candidate loop ledgers → validated → best one picked
       → per beat: 3 drafts → linter → 4 auditors → unanimity → best of 3
       → assembly → full-pass review → handoff
```

Three things carry the enforcement:

**The research pack is a closed set.** Every factual claim in the script must carry a
claim ID from the pack. A statement of fact without an ID fails whether or not it
happens to be true — which turns "did it hallucinate?" into a set-difference rather
than a judgment call. A second agent then re-verifies the pack against fresh sources,
because a fact that was wrong when gathered poisons everything downstream.

**The loop ledger makes structure checkable.** The story is a chain of nested questions:
one root question that can't be answered directly, decomposed into sub-questions that
overlap, so the listener never reaches a point where nothing is unresolved. That's
recorded as data and validated by script — no beat before the last may end with zero
open questions, every question that opens must pay off, and children must resolve
before their parents.

**Four auditors, not one.** A single generalist reviewer hedges across concerns and
approves the average. A fact auditor, a structure auditor, a prose auditor, and a cold
reader each reject on their own axis. Any one can reject; unanimity to advance. Each
runs as a separate `delegate_task` — an auditor that watched the writer reason will
defend the writer's choices.

Three drafts of everything, always. Approval is the entry fee, not the finish line.

### Layout

```
skills/story-forge/
├── SKILL.md
├── references/
│   ├── loop-ledger.md        # schema, nesting rules, worked example
│   ├── research.md           # sourcing standard, claim IDs, verification pass
│   ├── prose-rules.md        # banned constructions, rhythm, word choice
│   ├── review-protocol.md    # the four auditors, rubric, verdict schema
│   └── troubleshooting.md    # deadlocks, thin packs, failure modes
├── scripts/
│   ├── check_ledger.py       # validates the question-chain
│   └── lint_draft.py         # deterministic slop linter
└── assets/
    ├── ledger.json.tmpl
    ├── research-pack.json.tmpl
    ├── verdict.json.tmpl
    ├── writer-prompt.md.tmpl
    └── auditor-prompts.md.tmpl
```

### Install

```bash
hermes skills install shairkhan2/hermes-content-creator-/skills/story-forge
```

Then `/story-forge` in any Hermes session.

### The validators standalone

Both are stdlib-only Python 3.9+, usable outside Hermes.

```bash
python3 skills/story-forge/scripts/check_ledger.py ledger.json
python3 skills/story-forge/scripts/lint_draft.py draft.md --pack pack.json --budget 95
```

Exit `0` clean, `1` on findings, `2` on bad input. Add `--json` for machine-readable
output, `--strict` to treat warnings as failures.

### Tests

```bash
python3 -m pytest tests/ -q
```

The enforcement layer is itself tested — a linter that silently stops rejecting is
worse than no linter, because the pipeline keeps reporting approvals.

## License

MIT
