# Troubleshooting

## "Vertex AI API has not been used" / permission denied

The user has a Google AI Pro or Ultra subscription but not a billed GCP project. These
are separate routes: the subscription covers Flow and NotebookLM, which are UI products
with credit pools and **no API**. Nothing in this skill can reach them.

Check `GOOGLE_CLOUD_PROJECT` points at a real project, billing is enabled, and the Vertex
AI API is turned on for it. If the user only has the subscription, say so plainly — the
skill cannot run, and the honest fallback is to produce the shot list and prompts for
them to drive Flow by hand.

## Video and narration drift apart

Shot times tile the narration exactly, so drift means something broke the tiling.

1. Re-run `check_shotlist.py`. `timeline-gap`, `timeline-overlap`, and `timeline-short`
   all produce exactly this symptom.
2. Check whether `shotlist.json` was hand-edited. It is generated for a reason.
3. Check that every clip was rendered at its shot's `duration_s` and not at a default 8s.
   This is the most common cause: a run that ignores per-shot duration produces video
   longer than its audio, and the gap compounds with every shot.

Compare `ffprobe` duration on `final.mp4` against `voiceover.json`'s `duration_s`. More
than 0.2s apart is a real fault, not rounding.

## The middle of a clip turns to soup

Start and end frames are too far apart. Veo interpolates between them; it cannot invent a
cut, so when the two frames share nothing it fills the gap with mush.

Split the shot in two and add a hinge frame between. That is cheaper than fighting it
with prompt wording, and it is what the one-change rule exists to prevent.

## Style drifts across the render

If it drifts, the reproducibility gate in step 2 was skipped or the style string was
edited mid-render.

Style strings that lean on subject-specific words ("weathered steel", "industrial") read
as style on one subject and as content on another. Rewrite in terms of medium, light,
palette, and lens, then re-probe on two unrelated subjects.

Editing the style at shot 120 means shots 1–119 belong to a different film. If it truly
must change, re-render everything.

## Fixing one shot broke the one before it

A hinge frame belongs to two shots. Regenerating it to fix shot 7 changes shot 6's ending.

Re-render both clips or neither. Track which frames are hinges — `check_shotlist.py`
labels them, and any frame used twice is one.

## Ambience jumps between clips

Veo generates audio per clip independently, so room tone does not chain the way frames
do. Two visually continuous shots can have audibly different ambience.

Crossfade the **audio only** at clip boundaries. The video is continuous by construction
and needs no crossfade — adding one there would blur a chain that is already seamless.

## Generated audio contains speech

Veo sometimes produces voices. Under narration that reads as an error.

Catch it in the draft pass. Either re-render the shot with a prompt that steers away from
people talking, or mute that clip's audio specifically in the mix.

## Too many forced splits

`forced_split` means a clause ran longer than 8 seconds and had to be cut mid-sentence.
A few are fine. Many means the narration was marked too coarsely during TTS.

The fix is upstream: mark at finer clause granularity so the merger has real boundaries
to choose from. Splitting is what happens when it has none.

## The render is enormous

A 30-minute story is around 225 Veo calls and 280 Imagen calls — hours of wall clock and
a real bill.

`check_shotlist.py` warns above 150 shots. Surface the number to the user *before*
starting, run with `background=true` and `notify_on_complete=true`, and do the fast-model
draft pass first so a style problem does not cost the full render twice.

## Everything validates and the video is dull

The mechanical checks cannot see this, the same way the prose linter cannot see a boring
beat.

Watch it muted, end to end. If you cannot tell where beats end, the cuts are not landing
on the question chain — check that beat boundaries in `shotlist.json` match the ledger.
If every shot is a slow push-in, the motion budget was filled in mechanically. Vary it:
`reveal` on beats that pay off a question, `hold` where narration should carry alone.
