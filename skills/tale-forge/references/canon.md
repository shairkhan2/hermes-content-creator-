# The Canon

`story-forge` locks its writer to a research pack — facts with sources. Fiction has no
sources, so the lock becomes the canon: everything the story has established about its
own world.

The mechanism is the same closed set. The purpose is different. The pack prevents
stating something untrue; the canon prevents contradicting yourself.

## Why it exists

Continuity drift is what makes long fiction fall apart, and it is invisible while you
are writing. The ghost only appears in silence — until beat nine, when it appears
during a thunderstorm because that beat needed a scare. A character is thirty-seven in
beat two and "barely thirty" in beat eleven. The house has two floors and then a third.

None of these look wrong in the beat where they happen. They only look wrong from
outside, which is exactly what a beat-level auditor cannot see. So the canon is written
down and checked against, rather than remembered.

## Shape

```json
{
  "premise": "One sentence. What this story is.",
  "entities": [
    {
      "id": "E001",
      "kind": "character",
      "name": "Sarah Vance",
      "facts": ["37", "sound engineer", "moved in three weeks ago", "sleeps badly"]
    },
    {
      "id": "E002",
      "kind": "place",
      "name": "the fourth stair",
      "facts": ["creaks under any weight", "stopped creaking on the third night"]
    },
    {
      "id": "E003",
      "kind": "object",
      "name": "the baby monitor",
      "facts": ["left by the previous tenant", "receives a channel nobody transmits on"]
    }
  ],
  "rules": [
    {
      "id": "R001",
      "rule": "It only manifests in absolute silence.",
      "consequence": "Noise is safety. Every quiet room is a threat, and the character starts making noise on purpose."
    }
  ]
}
```

`kind` is `character`, `place`, `object`, or `concept`. `facts` are short and flat —
one assertion each, the way pack claims are.

## Rules are the load-bearing part

Everything above `rules` is bookkeeping. The rules are what make the story work.

**A threat with no limits has no tension.** If the ghost can do anything, anywhere, at
any time, the audience cannot tell what counts as a near miss — and a near miss is the
only thing that generates dread. Unlimited power reads as arbitrary, and arbitrary is
boring.

So write down what it cannot do. Under what conditions it appears. What it wants. What
it costs to see it. What makes it stop.

Then hold to them, especially when a beat would be easier if you didn't. A rule broken
for convenience is the moment the audience stops believing the story has a shape.

Good rules generate their own scenes:

| Rule | What it forces |
|---|---|
| Only manifests in absolute silence | The character makes noise deliberately; a power cut becomes unbearable |
| Cannot cross running water | The geography of the house becomes a map of safety |
| Appears one step closer each time you look away | Every glance is a choice, and not looking is worse |

Each of those writes a beat by itself. That is the test of a good rule: it does not
constrain the story, it produces it.

## Entities enter the canon before the prose

A named person, place, object, or rule must exist in `canon.json` before a draft can
use it. Inventing on the fly is precisely how act three contradicts act one.

The writer may propose additions — a beat often needs a detail nobody planned. The
sequence is: add it to the canon, then write it. Not the reverse.

The canon auditor rejects any named entity absent from the canon, which makes the
ordering enforceable rather than aspirational.

## What does not belong

Plot goes in the ledger, not the canon. The canon is what is *true* about the world;
the ledger is what *happens* and in what order.

If a fact only matters because of when it is revealed, it is still canon — the timing
belongs to the ledger, the fact belongs here.

## Aim for surplus

More canon than the story can use, same as the research pack. A writer choosing from an
abundant world writes better than one stretching four details across nine beats.

If beats keep failing on prose grounds, check the canon size before blaming the writer.
Thin worlds produce thin prose, and no amount of review fixes it downstream.
