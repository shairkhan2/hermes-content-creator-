# Style Derivation

The visual style is an output of the story before it is a constraint on the render. It
is read out of the finished script, argued three ways, tested, and only then locked.

## Why it is derived and not chosen

A style picked up front is a preference. A style derived from the story is an argument
about how *this* material should look — and the difference shows across two hundred
images. A war story and a story about a bureaucratic failure want different palettes,
different lens language, different light, and no default covers both.

It also has to be locked *early*, because it constrains every prompt that follows.
Deriving it late means re-rendering everything that came before.

## Three candidates, genuinely different

Same rule as the story ledger: three *approaches*, not three phrasings. If swapping one
candidate's palette into another changes nothing else, you designed once.

Each candidate is a complete argument:

```json
{
  "id": "A",
  "name": "Archival grain",
  "style_string": "16mm documentary photography, desaturated ochre and slate palette, hard side light, 35mm lens, visible grain, 1970s news stock",
  "negative_prompt": "clean digital, neon, lens flare, shallow depth of field, cgi",
  "palette": ["#3a4045", "#8a7a5c", "#c4b393", "#1c1f22"],
  "argument": "The story is about institutional failure recorded after the fact. It should look like evidence, not like drama."
}
```

Vary the things that actually change an image:

| Axis | Range |
|---|---|
| Medium | photographic, illustrated, painterly, graphic/flat, 3D |
| Palette | the four to six colours the whole piece lives inside |
| Light | hard/soft, direction, time of day, practical vs motivated |
| Lens | focal length, depth of field, height, distance from subject |
| Texture | grain, halation, cleanliness, era of the capture medium |

## The probe

Render the **same** scene for all three candidates with Imagen. Same subject, same
composition, same framing — the only variable is the style string.

Pick a probe scene that is representative of the story's actual content, not a generic
test card. A style that looks striking on a landscape and falls apart on a face is a
problem you want to find here, and most stories have faces.

## The audit

Delegate the comparison. The auditor sees the three probe images, their arguments, and
the story, and answers:

1. **Does it serve this story?** Or is it a look that would fit anything? Generic is the
   failure mode — the visual equivalent of prose slop.
2. **Is it distinctive?** Will it still read as one piece across two hundred images, or
   will it dissolve into stock?
3. **Is it reproducible?** See below. This one is objective and it outranks the others.

## The reproducibility gate

This is the check that earns its place, because it is the only one that is not taste.

Render the candidate's style string on **two unrelated subjects** — a face and a
landscape, an interior and an object. Then have Gemini vision compare them against each
other and against the probe.

A style that drifts across two probes will drift across four hundred keyframes. Finding
it now costs two images. Finding it after the render costs the render.

Score on:

- Palette consistency — are the same colours governing both?
- Light consistency — same quality and direction?
- Texture consistency — same grain, same apparent capture medium?
- Medium consistency — did one probe quietly become an illustration?

A candidate that fails reproducibility is out regardless of how good the probe looked.
Prompt strings that lean on subject-specific words ("weathered steel", "industrial")
are the usual cause — they read as style on one subject and as content on another.

## Locking it

The winner is written to `style.json` with its reference image:

```json
{
  "id": "A",
  "name": "Archival grain",
  "style_string": "...",
  "negative_prompt": "...",
  "palette": ["#3a4045", "..."],
  "reference_image": "style/reference.png",
  "probes": ["style/probe-a-face.png", "style/probe-a-landscape.png"],
  "locked": true
}
```

The reference image matters as much as the string. Words drift; an image used as
conditioning does not. Every keyframe prompt from here is
`style_string + subject + composition`, with the reference passed as conditioning and
`negative_prompt` applied.

Once locked, it does not change mid-render. A style edited at shot 120 means shots 1–119
belong to a different film.
