---
name: voice-forge
description: Narrate a script with exact timing via Vertex or ElevenLabs.
version: 0.1.0
author: shairkhan2, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [tts, voiceover, narration, vertex-ai, elevenlabs, timing, audio]
    related_skills: [story-forge, tale-forge, shot-forge]
    requires_toolsets: [terminal, file]
    requires_tools: [text_to_speech]
    config:
      - key: voice_forge.default_backend
        description: "TTS backend to suggest first when a project hasn't chosen one"
        default: ""
        prompt: "Default TTS backend (vertex, elevenlabs, or leave blank to always ask)"
required_environment_variables:
  - name: GOOGLE_CLOUD_PROJECT
    prompt: "Google Cloud project ID with Vertex AI enabled"
    help: "Only needed if the project chooses the vertex backend."
    required_for: "Vertex Cloud TTS calls"
    optional: true
  - name: ELEVENLABS_API_KEY
    prompt: "ElevenLabs API key"
    help: "Only needed if the project chooses the elevenlabs backend. https://elevenlabs.io/app/settings/api-keys"
    required_for: "ElevenLabs v3 calls"
    optional: true
---

# Voice Forge

Turns a finished script (`story-forge` or `tale-forge` output) into narration audio with
exact clause-level timing, in the shared `voiceover.json` shape `shot-forge` consumes.
Two backends are supported — Vertex Cloud TTS and ElevenLabs v3 — and **the choice is
asked per project, every time, never assumed.**

It does not write the script and does not touch video. It sits between the two.

## When to Use

- A story is finished (`story-clean.md` + `handoff.json` exist) and needs narration.
- The user wants to record or re-record voiceover for a project.
- `shot-forge` is blocked waiting on `voiceover.json`.

Don't use for:

- Writing the script — `story-forge` or `tale-forge`.
- Anything past the audio file and its timing — `shot-forge` takes it from here.
- A one-off "say this out loud" with no timing requirement. Call `text_to_speech` directly.

## Always ask which backend, every project

This is not a global default quietly applied. At the start of every project, ask:

> This project needs a narration voice. Two options:
> - **Vertex Cloud TTS** — same billing as the rest of the pipeline, SSML mark timing is
>   native and exact, voice selection is narrower.
> - **ElevenLabs v3** — broader and more expressive voice range, separate API key and
>   billing, timing is derived from character-level alignment rather than native marks.
>
> Which one for this project?

Use `clarify` (or the harness's equivalent question tool) to ask this explicitly. Do not
infer it from `voice_forge.default_backend` without confirming — that config exists to
pre-fill the suggestion, not to skip the question. A user running both a documentary
project and a horror-short project in the same Hermes install may reasonably want
different voices for each, and the skill must not collapse that choice into a global.

Record the answer in the project as `voice.json`:

```json
{"backend": "elevenlabs", "voice": "<voice id>", "chosen_at": "2026-08-18"}
```

Every later step in the same project reads this file rather than asking again. A new
project asks again.

## The two backends are not interchangeable in mechanism

| | Vertex Cloud TTS | ElevenLabs v3 |
|---|---|---|
| Timing source | SSML `<mark>` tags, named natively | Character-level alignment (no SSML marks) |
| Precision | Exact, per mark | Derived — offset lookup into alignment |
| Billing | Same GCP project as Imagen/Veo | Separate account and key |
| Voice range | Narrower | Broader, more expressive, more control |
| SSML support | Full | **v3 does not support SSML break tags** |

Both end up at the same `voiceover.json` shape. Getting there is different work, done by
`build_voiceover.py --backend <vertex|elevenlabs>`. Detail in `references/backends.md`.

## Prerequisites

Only the chosen backend's credentials are required — the other's env var is `optional`.

```
terminal(command="python3 --version", timeout=30)
```

## Procedure

### 1. Ask, and record the answer

Per the section above. Write `<project>/voice.json`. Do not proceed without it.

### 2. Split the script into clauses

Fine-grained, beat-aware clause boundaries — the same granularity `shot-forge` expects
to merge back up into shots.

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/split_clauses.py <project>/handoff.json --project-dir <project> -o <project>/clauses.json --emit-ssml <project>/ssml.xml --emit-plain <project>/plain.txt --emit-offsets <project>/offsets.json", timeout=60)
```

This always emits all four outputs; use whichever pair matches the chosen backend.

### 3a. Vertex path

Call Cloud TTS with the SSML from step 2, `enableTimePointing: ["SSML_MARK"]` (or the
current API's equivalent flag — confirm against live docs, this moves), and save the raw
JSON response.

```
terminal(command="<Cloud TTS call: ssml=<project>/ssml.xml, voice=<selected>, markTiming=on> > <project>/tts-response.json", timeout=300)
```

### 3b. ElevenLabs path

Call the v3 dialogue-with-timestamps endpoint with the plain text from step 2. A single
narrator is one entry in the dialogue list.

```
terminal(command="<ElevenLabs call: text=<project>/plain.txt, model=eleven_v3, endpoint=with-timestamps> > <project>/tts-response.json", timeout=300)
```

Save the decoded audio to `<project>/voiceover.<ext>` — the response returns base64 audio
alongside the alignment; decode before writing.

### 4. Normalize to voiceover.json

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/build_voiceover.py <project>/tts-response.json --backend <vertex|elevenlabs> [--offsets <project>/offsets.json] --clauses <project>/clauses.json --audio-file <project>/voiceover.wav --voice <voice-id> -o <project>/voiceover.json", timeout=60)
```

`--offsets` is required for `elevenlabs`, refused for `vertex` (there is nothing for it
to do there — Vertex marks are already named).

This is where a backend-specific failure surfaces: non-increasing marks, or — for
ElevenLabs — a character at a clause's offset that does not match the clause's own text,
meaning the text actually sent to the API drifted from `plain.txt`. Both are hard
failures. Do not proceed past either; the shot list built on bad timing will be silently
wrong in a way nothing downstream catches.

### 5. Verify

```
terminal(command="ffprobe -v error -show_entries format=duration -of csv=p=0 <project>/voiceover.wav", timeout=30)
```

Compare against `voiceover.json`'s `duration_s`. More than a fraction of a second apart
means the audio file and the timing response are not actually the same take — usually a
stale `tts-response.json` from a previous attempt.

## Quick Reference

```
python3 ${HERMES_SKILL_DIR}/scripts/split_clauses.py handoff.json --project-dir <dir> -o clauses.json
python3 ${HERMES_SKILL_DIR}/scripts/split_clauses.py handoff.json --project-dir <dir> --emit-ssml s.xml --emit-plain p.txt --emit-offsets o.json
python3 ${HERMES_SKILL_DIR}/scripts/build_voiceover.py response.json --backend vertex --audio-file vo.wav -o voiceover.json
python3 ${HERMES_SKILL_DIR}/scripts/build_voiceover.py response.json --backend elevenlabs --offsets offsets.json --audio-file vo.mp3 -o voiceover.json
```

Exit `0` ok, `1` alignment/timing problem, `2` bad input.

## Pitfalls

- **Never skip the question.** Even with `voice_forge.default_backend` set, confirm it
  for this project. Silent reuse of a prior project's choice is the failure mode this
  skill exists to prevent.
- **ElevenLabs v3 does not support SSML marks.** Do not attempt to port the Vertex SSML
  path over — the plain-text + offset path is the only one that works, and it is why
  `build_voiceover.py` has two genuinely different code paths rather than one.
- **The offset check is not paranoia.** If the text handed to the API differs from
  `plain.txt` by even a stray character — a copy-paste, a manual edit, a truncated
  request — every clause after the drift point gets the wrong timestamp, silently,
  unless the check catches it. It is designed to catch it.
- **Citations must be stripped before they reach the TTS.** `split_clauses.py` removes
  `[Cxxx]` markers and the space before them; if narration text is prepared any other
  way, check for stray citation brackets or double spaces before they're voiced.
- **A beat's text file must not be empty.** An empty beat produces zero clauses and
  `split_clauses.py` refuses to proceed rather than silently skip it.
- **Re-recording a project should ask again**, not reuse `voice.json` from the last run,
  unless the user explicitly says to keep the same voice.

## Verification

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/build_voiceover.py <response> --backend <b> --audio-file <f> -o <project>/voiceover.json", timeout=60)
```

- Exits `0`.
- Mark count in `voiceover.json` matches clause count in `clauses.json`.
- `voiceover.json`'s `duration_s` is within a fraction of a second of `ffprobe`'s
  measured duration on the actual audio file.
- `voice.json` records the backend actually used, for this specific project.

## References

| File | Contents |
|---|---|
| `references/backends.md` | Vertex vs ElevenLabs mechanism, API shapes, when to pick which |
| `references/clause-splitting.md` | How clauses are chosen, and why granularity matters |
| `references/troubleshooting.md` | Drift, non-increasing marks, missing alignment |
