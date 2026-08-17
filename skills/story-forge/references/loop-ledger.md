# The Loop Ledger

The ledger is the story's skeleton, designed and validated before a word of prose
exists. It records every question the story raises, where it raises it, where it
answers it, and which question it serves.

## Why structure comes first

A story that loses people does not lose them at the sentence level. It loses them at
the moment nothing is unresolved. Good sentences cannot fix that, and bad sentences
cannot break a structure that always has something open. So the ledger is where the
review passes are worth the most, and it is the one artifact validated by a script
rather than judged.

## The shape

One **root question** the whole piece answers. It has to be a question that cannot be
answered directly — if a sentence would do it, there is no story. It opens in beat 1
and closes in the final beat.

Underneath it, **sub-questions** that *can* be answered. Each one's answer sets up the
next one's premise. They overlap: a new question is planted before the previous one
closes, so the listener never reaches a resting point until the end.

```
beat   1     2     3     4     5     6     7     8     9
Q1  ├──────────────────────────────────────────────────┤   root, closes last
Q2  ├─────────────┤                                        opens with the root
Q3        ├─────────────┤                                  planted before Q2 closes
Q4                    ├─────────────┤
Q5                          ├─────────────┤
Q6                                ├─────────────────────┤  lands into the root
```

At no vertical slice before beat 9 is there only one bar. That is the whole design.

## Schema

`ledger.json`:

```json
{
  "root_question": "Why did a single ship stopping for six days cost the world $60 billion?",
  "total_beats": 9,
  "target_words": 750,
  "beats": [
    {"n": 1, "job": "Open the root question through one concrete image", "word_budget": 60}
  ],
  "questions": [
    {
      "id": "Q1",
      "text": "Why did a single ship stopping for six days cost the world $60 billion?",
      "parent": null,
      "opened_at": 1,
      "pays_off_at": 9
    }
  ]
}
```

| Field | Meaning |
|---|---|
| `root_question` | Must match the text of the one question with `parent: null` |
| `total_beats` | Number of beats; must equal `len(beats)` |
| `target_words` | Optional. Enables the budget-drift check |
| `beats[].n` | 1-indexed beat number |
| `beats[].job` | What this beat is *for*. Not a summary — a purpose |
| `beats[].word_budget` | Hard cap handed to the writer |
| `questions[].id` | `Q1`, `Q2`, … unique |
| `questions[].text` | Written as an actual question |
| `questions[].parent` | The question this one serves. `null` for the root only |
| `questions[].opened_at` | Beat where the listener first feels it |
| `questions[].pays_off_at` | Beat where it resolves. Must be > `opened_at` |

## `parent` means *serves*, not *follows*

This is the subtlety that trips up the first ledger everyone writes.

`parent` is a **containment** relation, not a sequence. Q4's parent is the question Q4
exists in service of — and a child must resolve before its parent does, because a
question cannot outlive the thing that gave it meaning.

If beat 4 answers Q3, and that answer raises a brand-new question, the new question is
**not** Q3's child. Q3 is closing. The new question serves whatever is still open —
usually the root. Hang it there.

```
Wrong:  Q3 opens 2, pays 4.  Q4 parent Q3, opens 4, pays 6.
        → child-outlives-parent. Q3 is dead by beat 4; Q4 cannot serve a dead question.

Right:  Q3 opens 2, pays 4.  Q4 parent Q1, opens 3, pays 6.
        → Q4 serves the root. It was *raised by* Q3's answer, which is a fact about
          the prose, not about the tree. Opening it at 3 rather than 4 also overlaps
          Q3 instead of seaming against it.
```

Use a real child when the sub-question is genuinely a component of its parent:
"why did it take six days?" is a component of "how does a ship this size get stuck?"
only if the six-days answer is *part of* the stuck answer. If it stands on its own,
it belongs to the root.

## The rules the script enforces

Run `python3 ${HERMES_SKILL_DIR}/scripts/check_ledger.py <ledger.json>`.

**Errors — these block the stage:**

| Code | Meaning |
|---|---|
| `orphan-question` | A question opens and never pays off |
| `instant-payoff` | Opens and closes in the same beat. Not a loop |
| `no-root` / `multiple-roots` | Zero or several `parent: null` questions |
| `root-closes-early` | Root does not pay off in the final beat |
| `child-outlives-parent` | See above — usually a `parent` that should be the root |
| `child-opens-before-parent` | The child exists before the question it serves |
| `parent-cycle` | Questions serving each other in a ring |
| `dead-beat` | Some beat before the last ends with no open sub-question |
| `beats-missing` / `beat-no-job` / `beat-no-budget` | Incomplete beat definitions |

**Warnings — judgment calls, but justify them:**

| Code | Meaning |
|---|---|
| `hard-seam` | A question closes and the only thing carrying across opened in that same beat |
| `root-opens-late` | The root normally opens the story |
| `crowded-ending` | More than one sub-question lands in the final beat |
| `question-not-a-question` | `text` does not end in `?` |
| `budget-drift` | Beat budgets sum >10% away from `target_words` |
| `uniform-budgets` | Every beat the same length — beats have different jobs |

`dead-beat` and `hard-seam` are the two that encode the actual storytelling rule. The
rest is hygiene.

`dead-beat` is the hard failure: nothing is open, the listener leaves. `hard-seam` is
the softer version — something *is* open across the handoff, but it only opened in the
very beat the previous question closed, so the story visibly stops and restarts instead
of carrying the listener across. Fix a seam by planting the next question a beat
earlier, never by delaying the current payoff.

## Writing three candidates

Step 4 asks for three ledgers. They must be three *structures*, not three phrasings.
Different root question, different entry point, different order of revelation.

If all three share a root question, you designed once and typed it out three times.
The tell: swap the root of A into B and nothing else has to change.

Good divergence on the same material:

- **A — mechanism first.** Root: why is this specific geography impossible to route
  around? Opens on a map, ends on economics.
- **B — person first.** Root: what does one captain see in the thirty seconds before
  a ship becomes unsteerable? Opens in a wheelhouse, ends on systems.
- **C — consequence first.** Root: why did a furniture shortage in Ohio start with
  wind in Egypt? Opens at the far end of the chain and works backwards.

## Long form: acts

Everything above describes a flat ledger — sub-questions hanging directly off the root.
That works to roughly 15 beats. Past that it validates and still reads as a list,
because nothing organises the middle.

For a 20-, 30-, or 60-minute piece, nest one level deeper:

```
Q1   root                              beat 1 ────────────────────────► end
 ├── A1  act question                  beats 1–15
 │    ├── B1  beat question            beats 1–4
 │    ├── B2                           beats 3–6      (overlapping)
 │    └── …
 ├── A2  act question                  beats 13–29    (opens before A1 closes)
 │    └── …
 └── A3  act question                  beats 27–end
      └── …
```

Rules that matter at this scale:

- **Act questions are questions, not headings.** "The middle section" is not an act
  question. "Why did the people who built it refuse to use it?" is. Each act closes
  something the listener has carried for ten minutes.
- **Acts overlap too.** A2 opens before A1 closes, exactly like beat questions. An act
  boundary where the next act opens only as the current one closes is the most common
  source of `hard-seam` in long form.
- **Beat questions nest inside their act,** not the root. A beat question serving A2
  must open and close within A2's span — the nesting rules apply at every depth.
- **A cascade at the end is correct.** The final beat question answers its act, the act
  answers the root, all in the last beat. `crowded-ending` only fires on siblings
  piling up, which is the actual failure it is looking for.

Depth is not limited to three. A 60-minute piece may want root → act → section → beat.
The validator handles any depth; the same nesting rules apply at each level.

## When no ledger validates

If all three candidates fail, the material does not support the requested length. Say
so. Offer a shorter target or a narrower topic.

Do not add beats to reach a duration. That is precisely the moment slop is created —
padding at the structural level, before a single sentence has been written.
