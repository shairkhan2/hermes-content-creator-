# Prose Rules

Rules for the writer, and the standard the prose auditor holds drafts to. The linter
enforces the mechanical half; everything here that a regex cannot see is the auditor's
job.

## The one rule underneath all the others

**Never write to reach a length.**

The writer is given a beat, its job, and a word cap. It is never given a duration or a
total target, because the moment a length becomes the goal, padding becomes the method
and padding is what slop *is*. A beat that does its job in 60 words against a cap of 95
is finished at 60. Under-budget is a warning, not an error, and the correct response to
it is to check the beat did its job — not to add words.

## Banned constructions

`lint_draft.py` hard-fails on these. The full list is `BANNED_PHRASES` in the script.
The categories:

**Register tells** — vocabulary that appears far more often in generated text than in
written English: `delve`, `tapestry`, `testament to`, `treasure trove`, `navigate the
complexities`, `in the realm of`, `seamless`, `robust`, `cutting-edge`,
`groundbreaking`, `revolutionize`, `unleash`.

**Throat-clearing** — words spent before the sentence starts: `it's important to note`,
`it's worth noting`, `when it comes to`, `in today's world`, `needless to say`,
`the fact of the matter is`, `at the end of the day`.

**Manufactured suspense** — tension asserted instead of built: `little did they know`,
`but here's the thing`, `plot twist`, `buckle up`, `let that sink in`, `the answer may
surprise you`, `that's where things get interesting`.

If the structure works, the suspense is already there. Reaching for these phrases is a
symptom that the ledger is not doing its job, and the fix is upstream.

**Connective padding** — `moreover`, `furthermore`, `additionally`, `that being said`.
Spoken narration does not need signposts between sentences. If two sentences need a
connective to relate, reorder them.

**Empty intensity** — `truly remarkable`, `absolutely stunning`, `nothing short of`,
`utterly`. Intensity comes from the fact, not the adjective in front of it.

## Unfalsifiable attribution — hard fail

`experts say`, `studies show`, `research suggests`, `many believe`, `it is said`,
`sources say`, `widely regarded`, `history tells us`.

Every one of these is a claim with the source deliberately removed. The pack has a
source or the claim does not exist, so there is never a reason to write one of these.

Replace with the actual source: not "studies show that 12% of trade passes through",
but "the canal authority puts it at 12%" — or cut it.

## Hedging — warned

`arguably`, `perhaps`, `somewhat`, `relatively`, `essentially`, `basically`, `quite`,
`rather`, `very`, `just`, `really`, `kind of`.

These drain a sentence without adding accuracy. Real uncertainty lives in the claim's
`confidence` field and gets stated explicitly — "nobody agrees on why" — rather than
smuggled in as a qualifier.

`very` and `just` are almost always deletable with no loss. Delete them.

## Rhythm

Spoken narration lives or dies on sentence-length variation. The linter measures the
standard deviation of sentence lengths and warns when they cluster — uniform rhythm is
the loudest tell of generated prose, louder than any individual word choice.

- Every beat needs at least one sentence under 7 words. It is where the listener lands.
- No sentence over 35 words. It will not survive being read aloud.
- Do not open three sentences in a row with the same word, and never four.
- Read every beat out loud. If you run out of breath, the sentence is wrong.

The pattern that works: long sentence carrying the detail, then a short one landing it.

> The wind came across the beam at forty knots, and on a ship stacked nine containers
> high the hull stops being a hull and starts being a sail. The bow swung.

## Verbs

The most common failure the auditor catches is a sentence with no verb doing any work:
`is`, `was`, `has`, `makes`, `becomes`, `provides` carrying the whole thing.

> The situation was complicated and difficult to resolve.

Nothing happens in that sentence. Name what was complicated:

> Two tugs pulled against a hull wedged into sand on both banks.

If a sentence's verb is `to be`, check whether a real verb is hiding in one of its nouns.

## Adverbs

The linter warns above 3.5% `-ly` density. An adverb propping up a weak verb means the
verb is wrong: not "moved slowly" but "crawled", not "said angrily" but "snapped".

Adverbs of time and degree that carry actual information are fine. Adverbs of manner
usually are not.

## Restatement

Padding to length shows up as the same beat delivered twice in different words. The
linter catches lexical overlap; it cannot catch a paraphrase that shares no vocabulary,
which is exactly what a model produces when stretching. That one is the prose auditor's.

The test: delete the sentence. If nothing is lost, it was restatement.

## Concrete over abstract

Every abstraction should be spent on something the listener can see.

| Abstract | Concrete |
|---|---|
| a massive vessel | four hundred metres of steel |
| significant economic disruption | shelves empty in Ohio |
| adverse weather conditions | a forty-knot crosswind |
| the situation escalated | ships behind her dropped anchor and waited |

The pack should already contain these — collecting concrete images is part of step 2.
If the writer has only abstractions available, the research was thin.

## Speaking, not writing

The output is read aloud. That changes what is correct:

- Contractions. "Nobody knew" not "No one did not know".
- Numbers a mouth can say. "About twelve percent", not "11.8%".
- No parentheticals. A voice cannot do brackets.
- No semicolons. Split the sentence.
- Names before pronouns, and re-introduce a name after two other subjects — a listener
  cannot scroll back.

## What the linter cannot see

The linter is objective, not smart. It will pass a draft that is accurate, budgeted,
cited, well-rhythmed, and boring. That is not a flaw in the linter — it is why the cold
reader exists.

Never treat a clean lint as an approval. It means the auditors start from a clean file.
