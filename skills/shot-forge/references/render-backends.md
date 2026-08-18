# Render Backends

The edit manifest holds the edit *decisions* — clip order, transitions, audio mix,
output spec. It says nothing about how they get rendered. A backend reads it and
produces a file.

That separation exists for one reason: **ffmpeg is what runs today, and it is not an
editor.** When something better is available, swapping it in should be a backend
change, not a rewrite of the pipeline.

## Current state

| Backend | Available | Can do | Cannot do |
|---|---|---|---|
| `ffmpeg` | yes | Hard cuts, audio mix, stream copy | Transitions, effects, keyframes, compositing |
| `opencut` | **no** | Cuts, dissolves, wipes, GPU effects, keyframes, masks | — |

`ffmpeg` is honestly named. It concatenates clips and mixes audio. Because every
boundary in a generated shot list is a cut, it can stream-copy — no re-encode, no
generation loss on the Veo output, and the render is exact.

What it cannot do is edit. There are no keyframed effects, no compositing, no
transitions beyond a hard join. That ceiling is a property of the tool, not of the
manifest, which is why the manifest can express things ffmpeg refuses.

## The capability gate

Each backend declares what it supports. `build_edit.py` checks the manifest against
the active backend and fails at **build** time rather than mid-render.

```
python3 ${HERMES_SKILL_DIR}/scripts/build_edit.py edit.json --check
python3 ${HERMES_SKILL_DIR}/scripts/build_edit.py edit.json --check --backend opencut
```

A manifest asking for a keyframed blur under `ffmpeg` produces:

```
ERROR  s0003: effect 'blur' unsupported by ffmpeg
ERROR  s0003: effect 'blur' is keyframed and ffmpeg cannot keyframe
```

**The table only lists what the emitter can actually generate.** `dissolve` is not in
ffmpeg's set even though ffmpeg has `xfade`, because the emitter does not build xfade
chains. A capability table that overstates its backend is worse than no table — it
moves the failure from build time to render time, which is exactly what the gate is
supposed to prevent.

When the emitter learns a new capability, it is added in one place and the gate opens.

## Render commands are generated, never hand-written

```
python3 ${HERMES_SKILL_DIR}/scripts/build_edit.py edit.json --emit ffmpeg
```

Emits the concat list, the join, the audio mix, and the verification probe, with paths
quoted and the expected duration inlined as a comment.

Hand-written ffmpeg in a procedure is how a backend gets welded to a pipeline. Keeping
the commands generated is what makes the swap a config change.

## Switching to OpenCut later

[OpenCut](https://github.com/OpenCut-app/OpenCut) is a real editor — GPU compositor,
multi-pass shader effects, keyframes, masks — and its rewrite roadmap names exactly
what this pipeline needs: an Editor API, headless mode for batch rendering, and an MCP
server for agents.

None of that is shipped. As of this writing the rewrite is early scaffolding, and the
usable version (`opencut-classic`) renders in-browser through WebCodecs with no CLI or
API. So `opencut` is declared as a backend and marked unavailable, which lets a
manifest be checked against it before it exists.

When the MCP server lands, the work is:

1. Flip `available` to `True` in `BACKENDS`.
2. Add an emitter that turns the manifest into MCP calls.
3. Confirm the declared capability set matches what it actually renders.

Nothing upstream of the manifest changes — not the shot list, not the keyframes, not
the clips. Only the last step.

## What does not belong in the manifest

The manifest is the **edit**, not the generation. Keyframe prompts, style strings, Veo
motion prompts, and shot timing all live in `shotlist.json` and `style.json`, upstream
of any backend.

Rule of thumb: if a different renderer would need it, it belongs in the manifest. If it
only concerns how the source clips were made, it does not.
