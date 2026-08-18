# Troubleshooting

## The backend question got skipped

If a project has `voiceover.json` but no `voice.json`, the question was never asked or
the answer was never recorded. Stop and ask before generating anything — do not infer
the backend from which fields happen to be present in an existing response file.

## ElevenLabs: `char_offset ... is outside the alignment`

The offset points past the end of the alignment array — the text sent to the API is
shorter than `plain.txt`, almost always because a beat was truncated, whitespace was
collapsed by something in the request path, or a retry sent an earlier draft.

Fix: regenerate `plain.txt` and `offsets.json` together from `split_clauses.py`, confirm
byte-for-byte that the string sent to the ElevenLabs request matches `plain.txt` exactly
(no encoding surprises, no trailing-newline mismatch), and re-call the API.

## ElevenLabs: `expected clause to start with ... alignment has ...`

The character at a clause's claimed offset does not match the clause's own text. This
means the alignment and the offsets disagree about what text was actually spoken — the
API received something other than exactly `plain.txt`.

This is the failure the check exists to catch, and it fails loudly on purpose: a timing
bug here does not look wrong, it looks like a slightly-off shot list three stages later,
which is a much worse place to debug it.

Fix the same way as the offset-out-of-range case: regenerate both files together and
confirm the exact request body matches `plain.txt`.

## Vertex: `response has no 'timepoints' list`

Either the SSML was sent without `<mark>` tags, or the request did not ask for mark
timing, or the selected voice does not support it. Confirm the current Vertex Cloud TTS
API's mark-timing parameter — it has moved between API versions — and smoke-test one
short clause before trying a full script.

## Marks are not strictly increasing

Both backends' outputs are checked for this because a non-increasing sequence means
`shot-forge`'s shot builder will see negative-duration or zero-duration clauses and fail
loudly there instead — better to catch it here where the cause is still visible.

For Vertex this usually means duplicate mark names in the SSML (two clauses given the
same mark by mistake). For ElevenLabs it usually means two offsets pointing at the same
or an out-of-order character position — check `split_clauses.py`'s output wasn't
hand-edited after generation.

## Audio duration doesn't match `voiceover.json`

`ffprobe` on the actual file disagrees with `duration_s` in `voiceover.json` by more
than a fraction of a second. This almost always means the audio file and
`tts-response.json` are from different takes — a `voiceover.wav` left over from a
previous run, or a response saved before a retry that produced new audio.

Regenerate both in the same call and re-run `build_voiceover.py` against the matching pair.

## A beat produces zero clauses

`split_clauses.py` refuses to proceed rather than silently skip an empty beat. Check the
beat's `text_file` actually has content — an empty file usually means a path was wrong
in `handoff.json`, or the writing stage failed to write that beat.

## Re-recording with a different voice mid-project

Ask again rather than reusing `voice.json`, unless the user explicitly says to keep the
existing choice. A user picking a new voice almost always wants the whole narration
re-generated with it, not a silent carry-over of the old backend for continuity's sake.
