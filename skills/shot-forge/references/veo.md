# Veo 3.1 on Vertex

Reference for the generation call. Confirm current parameters against
[the Vertex docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-first-and-last-frames)
before a large run — model ids and limits move.

## Models

| Model | Use |
|---|---|
| `veo-3.1-generate-001` | Final renders |
| `veo-3.1-fast-generate-001` | Draft passes over the whole story |

First-frame + last-frame interpolation requires a 3.1 model. Earlier Veo versions accept
a first frame only, which cannot express the chain.

## The call

Per shot: start frame, end frame, motion prompt, duration.

- **Duration is capped at 8 seconds.** Not a default — a ceiling. Pass the shot's actual
  duration from `shotlist.json` so the clip matches its slice of narration exactly.
- Both frames must share aspect ratio and resolution.
- Long-running operation: poll, or run through `terminal` with `background=true` and
  `notify_on_complete=true`. A few hundred shots is hours of wall clock.

## The motion prompt

Describes the **change**, not the content. The frames already carry the content;
repeating it in the prompt fights them.

```
Good:  "slow push in, camera drifts left as the hull fills frame"
Bad:   "a large container ship wedged in a canal, aerial view, dramatic"
```

The second describes the frames. Veo already has the frames. What it does not know is
how to get from one to the other.

Keep it to one clause. If the prompt needs "and", the shot is two shots — see the motion
budget in `references/keyframes.md`.

## Native audio

Veo 3.1 generates audio alongside video: ambience, foley, room tone.

Keep it. Mixed well under the narration it gives each shot a sense of place that a
silent clip does not have, and it costs nothing extra since it comes in the same pass.

It becomes an **ambience bed**, not a competitor. `shot_forge.ambience_db` defaults to
-24 dB under the narration. Two things to watch:

- **Speech in generated audio.** Veo will occasionally produce voices. Under narration
  that reads as a mistake. Catch it in the draft pass and either re-render the shot or
  mute that clip specifically.
- **Discontinuity at chain points.** Ambience does not chain the way frames do, so room
  tone can jump between two clips that are visually continuous. A short crossfade at
  clip boundaries fixes it; the video needs no crossfade, only the audio.

## Drafting

Render the whole story with the fast model before committing to full quality.

The point is not to save money — it is that style problems are only visible in motion.
A palette that looks right across still keyframes can strobe once it moves, and you want
that discovered across 200 fast clips rather than 200 slow ones.

Watch the draft muted, end to end, before the final pass.

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Middle of clip is soup | Frames too far apart | Split into two shots, add a hinge |
| Clip looks frozen | Frames near-identical | Widen the change, or accept `hold` |
| Subject morphs | Frames disagree about what the subject is | Re-render the hinge; check it works for both shots |
| Clip is soft | Keyframes below render resolution | Regenerate frames at or above target |
| Motion ignores the prompt | Prompt describes content, not change | Rewrite as a change |
| Ambience jumps at a cut | Independent generation per clip | Crossfade audio only, not video |

## Cost and scale

Roughly 6–8 shots per beat of narration. A 5-minute story is ~36 clips and ~45 frames; a
30-minute story is ~225 clips and ~280 frames.

`check_shotlist.py` warns above 150 shots. Tell the user the number before starting, not
after — and run in the background so the session is not blocked for hours.
