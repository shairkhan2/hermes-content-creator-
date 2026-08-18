# hermes-content-creator

Hermes Agent skills for content creation. Two skills so far, chained by a file contract rather than a shared runtime:

| Skill | Takes | Produces |
|---|---|---|
| **Story Forge** | a topic | `story-clean.md` + `handoff.json` |
| **Shot Forge** | `handoff.json` + `voiceover.json` | `final.mp4` |

The voiceover stage between them is not built yet — `voiceover.json` is a documented input contract that any TTS emitting SSML mark timepoints can satisfy.

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

Duration is an input, not a limit — 60 seconds to an hour and beyond. Past ~15 beats
the ledger nests into acts so the middle of a long piece has a spine instead of a list.

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

## Shot Forge

Renders a narrated script to video on Vertex AI. It derives a visual style *from the
story*, cuts a shot list against real audio durations, generates chained keyframes, and
bridges each pair with Veo 3.1.

**Timing comes from the audio, never an estimate.** Cloud TTS returns SSML mark
timepoints, so shot boundaries are chosen against exact numbers. (Transcribing your own
synthetic speech to recover timing it already gave you only adds error.)

**8 seconds is a hard Veo ceiling**, so it becomes the shot rhythm rather than a limit.
Chaining removes the need for any single clip to run longer: consecutive shots in a beat
share a keyframe — the end of one clip *is* the start of the next, the same PNG — so
continuity is structural instead of prompted and drift cannot accumulate. Beat
boundaries hard-cut, landing the edit where the story's question chain turns.

**Style is derived, then locked.** Three candidate looks are argued from the finished
story, probed with Imagen, and audited. The gate that decides it is reproducibility:
render a style on two unrelated subjects and compare. A style that drifts across two
probes will drift across four hundred keyframes, and finding out now costs two images.

**The renderer is swappable.** Edit decisions land in a backend-agnostic manifest;
a backend turns them into a file. Today that backend is ffmpeg, which is honest about
what it is — it concatenates clips and mixes audio, and because every boundary is a cut
it stream-copies with no re-encode. It is not an editor: no transitions, no effects, no
keyframes. Backends declare capabilities, so a manifest asking for more fails at build
time rather than mid-render, and the ffmpeg table lists only what its emitter can
actually generate.

[OpenCut](https://github.com/OpenCut-app/OpenCut) is the intended replacement — a real
editor with a GPU compositor, shader effects, and keyframes, whose roadmap names an
Editor API, headless mode, and an MCP server. None of it has shipped yet, so `opencut`
is declared as a backend and marked unavailable. When it lands, the swap is a new
emitter reading the same manifest; nothing upstream changes.

Requires a **billed GCP project with Vertex AI enabled**. Google AI Pro/Ultra covers Flow
and NotebookLM, which are UI products with no API — a subscription alone cannot run this.

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

skills/shot-forge/
├── SKILL.md
├── references/
│   ├── style-derivation.md   # three candidates, probe, reproducibility gate
│   ├── shot-list.md          # clause merging, the 8s ceiling, chaining and cuts
│   ├── keyframes.md          # Imagen prompting, hinge frames, motion budget
│   ├── veo.md                # Veo 3.1 on Vertex: params, first/last frame, audio
│   ├── render-backends.md    # backend contract, ffmpeg's ceiling, the OpenCut swap
│   └── troubleshooting.md    # drift, mush, desync, auth
├── scripts/
│   ├── build_shotlist.py     # timepoints -> shots under the ceiling
│   ├── check_shotlist.py     # validates the timeline and the chain
│   └── build_edit.py         # edit manifest + backend capability gate
└── assets/
    ├── voiceover.json.tmpl   # the input contract
    ├── shotlist.json.tmpl
    └── style.json.tmpl
```

### Install

```bash
hermes skills install shairkhan2/hermes-content-creator-/skills/story-forge
hermes skills install shairkhan2/hermes-content-creator-/skills/shot-forge
```

Then `/story-forge` or `/shot-forge` in any Hermes session.

### The validators standalone

Both are stdlib-only Python 3.9+, usable outside Hermes.

```bash
python3 skills/story-forge/scripts/check_ledger.py ledger.json
python3 skills/story-forge/scripts/lint_draft.py draft.md --pack pack.json --budget 95
python3 skills/shot-forge/scripts/build_shotlist.py vo.json -o shotlist.json
python3 skills/shot-forge/scripts/check_shotlist.py shotlist.json --require-prompts
python3 skills/shot-forge/scripts/build_edit.py shotlist.json -o edit.json
python3 skills/shot-forge/scripts/build_edit.py edit.json --emit ffmpeg
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
