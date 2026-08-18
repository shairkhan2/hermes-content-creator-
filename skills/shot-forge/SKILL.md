---
name: shot-forge
description: Build keyframe-chained video from a narrated script.
version: 0.1.0
author: shairkhan2, Hermes Agent
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [video, veo, imagen, vertex-ai, keyframes, storyboard, shot-list, narration]
    related_skills: [story-forge]
    requires_toolsets: [terminal, file]
    config:
      - key: shot_forge.veo_model
        description: "Veo model for clip generation"
        default: "veo-3.1-generate-001"
        prompt: "Veo model (veo-3.1-generate-001, or -fast- for drafts)"
      - key: shot_forge.imagen_model
        description: "Imagen model for keyframe stills"
        default: "imagen-4.0-generate-001"
        prompt: "Imagen model for keyframes"
      - key: shot_forge.workspace
        description: "Directory where render projects are created"
        default: "~/shot-forge"
        prompt: "Where should render projects be written?"
      - key: shot_forge.ambience_db
        description: "Level for Veo's native audio under the narration bed"
        default: -24
        prompt: "Ambience level in dB under narration (-24 is a quiet bed)"
required_environment_variables:
  - name: GOOGLE_CLOUD_PROJECT
    prompt: "Google Cloud project ID with Vertex AI enabled"
    help: "Must be a GCP project with billing. A Google AI Pro/Ultra subscription is a separate route and does not grant Vertex API access."
    required_for: "every Imagen and Veo call"
  - name: GOOGLE_CLOUD_REGION
    prompt: "Vertex AI region (us-central1 is the safe default)"
    help: "Veo and Imagen availability varies by region; us-central1 has the widest coverage."
    required_for: "Vertex endpoint resolution"
---

# Shot Forge

Takes a finished narration script plus its voiceover timing and renders video: derives
a visual style from the story, cuts a shot list against real audio durations, generates
chained keyframes, and bridges each pair with Veo. It does not write the script and
does not produce the voiceover — it consumes both.

Everything runs on Vertex AI. Google Flow and NotebookLM have no API and cannot be
driven from a skill, so a subscription alone is not enough to run this.

## When to Use

- A narration script and its voiceover exist, and the user wants video for it.
- The user asks for a storyboard or shot list from a timed script.
- The user wants a visual style derived from a story rather than picked in advance.

Don't use for:

- Writing the story. That is `story-forge`.
- Producing the voiceover. This skill consumes `voiceover.json`; it does not create it.
- A single clip from a single prompt. Call `video_generate` directly.
- Editing footage the user already has. Use ffmpeg through `terminal`.

## Prerequisites

- **A GCP project with billing and the Vertex AI API enabled.** This is the one that
  trips people up: Google AI Pro/Ultra gives Flow and NotebookLM, which are UI products
  with credit pools and no API. Vertex is a separate route with separate billing. If
  the user has only the subscription, stop and say so — this skill cannot run.
- `gcloud` authenticated, or a service account key with the Vertex AI User role.
- `ffmpeg` for concatenation and the audio mix.
- Python 3.9+ for the two scripts. No third-party packages.

```
terminal(command="gcloud auth application-default print-access-token >/dev/null && echo auth ok", timeout=60)
terminal(command="ffmpeg -version | head -1", timeout=30)
```

## Inputs

Two artifacts, both required before anything renders.

**`handoff.json`** — from `story-forge`. Supplies the title, the root question, and the
beat structure that decides where cuts land.

**`voiceover.json`** — the narration audio and its timing. Schema in
`assets/voiceover.json.tmpl`:

```json
{
  "audio_file": "voiceover.wav",
  "duration_s": 302.4,
  "marks": [
    {"name": "b01c01", "time_s": 0.0, "text": "She was four hundred metres of steel"},
    {"name": "b01c02", "time_s": 3.9, "text": "and she turned sideways"}
  ]
}
```

Mark names are `b<NN>c<NN>` — beat number, clause number. A mark records where a clause
*starts*; it ends where the next one begins.

These come from Cloud TTS SSML `<mark>` timepoints. Do not derive them by transcribing
the synthesised audio — the timing is already exact in the TTS response, and running it
back through speech-to-text only introduces error.

## The Rules

1. **Timing comes from the audio, never from an estimate.** The script's word budgets
   were a planning fiction. Real durations decide every shot boundary.
2. **8 seconds is a hard API ceiling.** Veo renders at most 8s per call. A longer shot
   cannot be rendered, so it is an error, not a warning.
3. **Chain within a beat, cut between beats.** Consecutive shots in a beat share a
   keyframe — the end of one clip *is* the start of the next. Beat boundaries hard-cut,
   so the edit lands where the story's question chain turns.
4. **One change per shot.** Camera, or subject, or reveal. Not several at once.
5. **Style is derived, then locked.** It comes out of the finished story, gets audited,
   and then constrains every prompt after it. It is never picked up front.
6. **Validate before rendering.** A fault caught in the shot list costs nothing. The
   same fault caught after generation costs hundreds of Veo calls.

## Pipeline

```
handoff.json + voiceover.json
      │
      ├─ build_shotlist.py ──► shotlist.json      (clauses merged into ≤8s shots)
      │
      ├─ style derivation ───► style.json         (3 candidates → audited → locked)
      │
      ├─ Imagen ─────────────► frames/*.png       (chained: end of N = start of N+1)
      │
      ├─ Veo 3.1 ────────────► clips/*.mp4        (first frame + last frame → 8s clip)
      │
      └─ ffmpeg ─────────────► final.mp4          (concat + narration over ambience)
```

## Procedure

### 1. Build the shot list

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/build_shotlist.py <project>/voiceover.json --handoff <project>/handoff.json -o <project>/shotlist.json", timeout=120)
```

Merges clauses into shots under the ceiling, assigns chained frame ids, and marks beat
heads as cuts. A clause longer than 8s on its own is split mid-sentence and flagged
`forced_split` — the audio is untouched, only the visual is cut.

Validate immediately:

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_shotlist.py <project>/shotlist.json", timeout=60)
```

Completion: exit 0, and the reported shot count matches what the user was told to expect.

### 2. Derive the style

The style comes out of the story, not out of a preference. Read the finished script,
then produce **three distinct visual approaches** — different medium, palette, lighting,
and lens, each one an argument about how this particular story should look.

For each candidate, write a style string, a negative prompt, and a palette, then render
the **same** probe scene with Imagen so the three are comparable.

Audit with `delegate_task` against three questions:

- Does it serve *this* story's mood and subject, or is it generic?
- Is it distinctive enough to recognise across 200 images?
- **Is it reproducible?**

Reproducibility is the objective gate, and it is the one that matters. Render the style
string on two unrelated subjects and have Gemini vision compare them. A style that
drifts across two probes will drift across four hundred keyframes, and finding out now
costs two images instead of the whole render.

Lock the winner to `style.json` with its reference image. Every prompt from here
inherits it.

Detail: `references/style-derivation.md`.

### 3. Write frame and shot prompts

For each frame in `shotlist.json`, write a prompt: style string, then subject, then
composition. For each shot, write the motion prompt describing the change between its
two frames, and set `motion` to `camera`, `subject`, `reveal`, or `hold`.

Hinge frames carry a double obligation — a frame is the end of one shot and the start
of the next, so it must satisfy both. Write hinges first, then the shots around them.

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_shotlist.py <project>/shotlist.json --require-prompts --require-motion", timeout=60)
```

Completion: exit 0 with both flags.

### 4. Generate keyframes

Imagen, in frame id order, using the locked style reference as conditioning. Write to
`frames/<frame_id>.png`.

Generate frames **before** any clip. A bad frame is one Imagen call to fix; the same
error found after the clips are rendered invalidates every clip that touched it.

Spot-check with `vision_analyze` against the style reference. Because frames are shared
between shots, one bad hinge breaks two clips.

### 5. Render clips

For each shot, call Veo 3.1 with its start and end frame and its motion prompt.

```
terminal(command="<veo call: model=$VEO_MODEL, image=frames/<start>.png, lastFrame=frames/<end>.png, prompt=<motion>, durationSeconds=<duration>>", timeout=900, background=true, notify_on_complete=true)
```

Use the `-fast-` model variant for a draft pass over the whole story before committing
to the full-quality render. Cheaper to discover a style problem across 200 fast clips
than across 200 slow ones.

Veo generates native audio. Keep it — it becomes the ambience bed under the narration,
not a competitor to it. Mixed at `shot_forge.ambience_db` in step 6.

Detail: `references/veo.md`.

### 6. Assemble

Concatenate clips in shot order, then lay the narration over the ambience bed:

```
terminal(command="ffmpeg -f concat -safe 0 -i clips.txt -c copy <project>/silent.mp4", timeout=600)
terminal(command="ffmpeg -i <project>/silent.mp4 -i <project>/voiceover.wav -filter_complex \"[0:a]volume=-24dB[amb];[amb][1:a]amix=inputs=2:duration=first[a]\" -map 0:v -map \"[a]\" -c:v copy <project>/final.mp4", timeout=600)
```

Confirm the render matches the narration exactly — any drift means a shot boundary was
edited by hand after the shot list was built.

```
terminal(command="ffprobe -v error -show_entries format=duration -of csv=p=0 <project>/final.mp4", timeout=60)
```

## Quick Reference

```
python3 ${HERMES_SKILL_DIR}/scripts/build_shotlist.py vo.json --handoff h.json -o shotlist.json
python3 ${HERMES_SKILL_DIR}/scripts/build_shotlist.py vo.json --max-shot 8.0 --min-shot 1.5
python3 ${HERMES_SKILL_DIR}/scripts/check_shotlist.py shotlist.json
python3 ${HERMES_SKILL_DIR}/scripts/check_shotlist.py shotlist.json --require-prompts --require-motion
python3 ${HERMES_SKILL_DIR}/scripts/check_shotlist.py shotlist.json --json --strict
```

Both exit `0` clean, `1` on findings, `2` on bad input.

## Pitfalls

- **A subscription is not Vertex access.** Google AI Pro/Ultra covers Flow and
  NotebookLM. Neither has an API. Confirm a billed GCP project before promising a render.
- **Never transcribe your own TTS to get timing.** Cloud TTS returns SSML mark
  timepoints directly. Speech-to-text on synthetic audio can mishear it, and you would
  be replacing exact numbers with inferred ones.
- **A hinge frame belongs to two shots.** Regenerating it to fix shot 7 changes shot 6.
  Re-render both clips or neither.
- **Too much change between frames produces mush.** Veo interpolates; it does not
  invent a cut. If start and end share nothing, the middle is soup. That is what the
  one-change rule is for.
- **Too little change produces a still.** `hold` is a legitimate motion, but a whole
  story of holds is a slideshow.
- **Draft with the fast model.** Discovering a style problem after 200 full-quality
  renders is an expensive way to learn it.
- **Don't hand-edit `shotlist.json` timings.** They tile the narration exactly. Change
  one and the audio desyncs from that point on. Rebuild from `voiceover.json` instead.
- **Scale is not a surprise.** A 30-minute story is roughly 225 clips and 450 frames.
  Tell the user the count and run in the background with `notify_on_complete`.

## Verification

```
terminal(command="python3 ${HERMES_SKILL_DIR}/scripts/check_shotlist.py <project>/shotlist.json --require-prompts --require-motion", timeout=60)
terminal(command="ffprobe -v error -show_entries format=duration -of csv=p=0 <project>/final.mp4", timeout=60)
```

- Shot list exits 0 with both flags.
- `final.mp4` duration is within 0.2s of `voiceover.json`'s `duration_s`.
- `frames/` holds exactly `frame_count` images, `clips/` exactly `shot_count` clips.
- Every beat boundary is a visible cut; nothing inside a beat is.
- Watch it muted. If you cannot tell where one beat ends and the next begins, the cuts
  are not landing on the question chain.

## References

| File | Contents |
|---|---|
| `references/style-derivation.md` | Three candidates, the probe, the reproducibility gate |
| `references/shot-list.md` | Clause merging, the 8s ceiling, chaining and cuts |
| `references/keyframes.md` | Imagen prompting, hinge frames, the motion budget |
| `references/veo.md` | Veo 3.1 on Vertex: parameters, first/last frame, native audio |
| `references/troubleshooting.md` | Drift, mush, desync, auth, and what each one means |
