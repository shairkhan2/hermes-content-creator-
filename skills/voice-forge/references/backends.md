# Vertex vs ElevenLabs

Both end at the same `voiceover.json` — marks named `b<NN>c<NN>`, each with an exact
`time_s`. They get there by mechanisms different enough that `build_voiceover.py` has
two real code paths, not one path with a flag.

## Vertex Cloud TTS

Timing comes from SSML `<mark name="b01c01"/>` tags placed at each clause boundary. The
API is asked to time-point marks (the exact request flag moves between API versions —
confirm against live Vertex docs before a large run) and the response echoes back a
`timepoints` list: `[{"markName": "b01c01", "timeSeconds": 3.92}, ...]`.

This is a **direct read**. The mark names in the response are the mark names you sent.
`build_voiceover.py --backend vertex` reshapes the response; it does not derive anything.

Failure mode: a voice or API version that does not support mark timing returns audio
with no `timepoints`. `build_voiceover.py` refuses rather than silently emitting an
empty `voiceover.json` — check the voice supports it before committing to a large script.

## ElevenLabs v3

**v3 does not support SSML break tags**, and there is no mark mechanism at all. Instead,
the with-timestamps endpoints return character-level alignment for the entire utterance:

```json
{
  "alignment": {
    "characters": ["S", "h", "e", " ", "w", "a", "s", ...],
    "character_start_times_seconds": [0.01, 0.05, 0.08, 0.10, ...],
    "character_end_times_seconds": [0.04, 0.07, 0.10, 0.13, ...]
  }
}
```

There is no clause information in this at all — only a timestamp per character of the
plain text you sent. Getting clause timing out of it means knowing, in advance, exactly
which character index each clause starts at within the text you sent, then reading that
index's `character_start_times_seconds`.

That is what `split_clauses.py --emit-plain --emit-offsets` produces: the exact string
to send to the API, and each clause's character offset within that exact string,
generated together in the same loop so they cannot disagree.

**This is the fragile direction.** If the text actually sent to ElevenLabs differs from
`plain.txt` by even one character — a copy-paste through something that normalizes
whitespace, a retry that used an edited version, a model that "cleaned up" the text
before sending — every offset after the drift point points at the wrong character, and
every clause after it gets the wrong timestamp. Silently, unless it's checked.

`build_voiceover.py --backend elevenlabs` checks: at each clause's claimed offset, does
the alignment's character actually match the clause's own first character? A mismatch
is a hard failure, not a warning, because a timing bug here does not announce itself —
it just produces a shot list that's plausible-looking and wrong.

`model_id` defaults to `eleven_multilingual_v2` on the plain TTS endpoints; v3 timing
specifically requires the **dialogue** with-timestamps endpoint, even for a single
narrator (one entry in the dialogue list).

## When to pick which

| | Vertex | ElevenLabs |
|---|---|---|
| Already paying for Vertex (Imagen, Veo) | One bill, one project | Second account, second key |
| Voice needs to be expressive / characterful | Narrower range | v3 is built for this |
| Timing needs to be bulletproof with zero derivation | Native marks | Derived, checked, but derived |
| Multiple projects, different voices per project | Fine either way — `voice.json` is per-project | Fine either way |

Neither is a default. The skill asks per project because a documentary project and a
horror-short project in the same install may reasonably want different answers, and
picking silently for the user removes a decision that is genuinely theirs.

## Verify before a large run

API shapes for both providers move. Before committing an hour of narration to either
path, do a one-clause smoke test: split one beat, call the API, run
`build_voiceover.py`, and confirm the mark count and timing look sane before running the
whole script through it.
