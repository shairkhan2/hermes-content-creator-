# Keyframes

Every clip is defined by two stills. Get the stills right and Veo's job is easy; get
them wrong and no motion prompt rescues the clip.

Frames are also the cheap layer. An Imagen call costs a fraction of a Veo call and
returns in seconds. Every problem worth catching should be caught here.

## Prompt structure

Three parts, in this order, every time:

```
<style_string> | <subject and action> | <composition>
```

- **Style** comes verbatim from the locked `style.json`. Never paraphrased, never
  trimmed to fit — a reworded style string is a different style.
- **Subject** is what is in frame and what it is doing.
- **Composition** is shot size, angle, and where the subject sits in frame.

The locked reference image is passed as conditioning, and `negative_prompt` is applied
to every call. Words drift across hundreds of images; the reference does not.

## Hinge frames carry two obligations

An interior frame is the end of one shot and the start of the next. It has to work as
both — the resolution of the motion before it and the setup for the motion after.

Write hinges first, then the shots around them. Writing shots first produces hinges that
are a compromise between two prompts nobody reconciled.

The consequence to remember: **regenerating a hinge to fix shot 7 also changes shot 6.**
Re-render both clips or neither. This is the most common way a render quietly desyncs
from its own frames.

## The motion budget

One change between start and end. Declared in `shotlist.json` as `motion`:

| Motion | The change | Good for |
|---|---|---|
| `camera` | Frame moves, subject does not | Establishing, revealing scale, pressure |
| `subject` | Subject moves, frame does not | Action, gesture, consequence |
| `reveal` | Something enters or becomes visible | Turns, payoffs, the moment a question lands |
| `hold` | Almost nothing moves | Weight, stillness, letting narration carry |

Two failure modes, in both directions:

**Too much change → mush.** Veo interpolates between your frames; it does not invent a
cut. Ask it to move the camera, move the subject, and change the light at once and the
middle becomes soup. Most bad keyframe video is exactly this.

**Too little change → a still.** If start and end are near-identical, you rendered an
expensive freeze frame. `hold` is legitimate and useful, but a story of holds is a
slideshow.

The test before rendering: describe the change in one clause. If it needs "and", it is
two shots.

## Continuity comes from the file, not the prompt

Chained shots share a frame *file*. Not a similar image, not the same prompt — the same
PNG. That is what makes the chain hold across a beat, and it is why prompt-per-clip
pipelines drift and this one does not.

Within a beat, only the hinges need to be consistent with each other, and they are
consistent by construction.

Across beats there is a hard cut, so continuity is a matter of style, not of frames.
That is the locked style string's job.

## Generate frames before clips

All frames first, then all clips. Never interleave.

A bad frame is one Imagen call to fix. The same error found after the clips are rendered
invalidates every clip that touched it — and if it is a hinge, that is two clips, not one.

Spot-check with `vision_analyze` against the style reference before any clip is rendered.
Check for the things that drift: palette wandering, the medium quietly turning into
illustration, light direction flipping between shots in the same beat.

## Aspect ratio and resolution

Set once, in the style lock, and never per shot. Mixed aspect ratios across a chain
break the chain — a frame that is the end of a 16:9 shot cannot be the start of a 9:16
one.

Generate frames at or above the target render resolution. Upscaling a keyframe before
handing it to Veo produces a soft clip that no amount of prompting sharpens.
