# Research and the Claim Pack

The pack is the writer's entire permitted universe of fact. If a statement is not in
the pack, the writer may not make it. That single constraint turns "did the model
hallucinate?" from a judgment call into a set-difference.

## Sourcing standard

Prefer, in order:

1. **Primary** — the paper, the filing, the transcript, the dataset, the court record,
   the manufacturer's spec, the raw footage.
2. **Reporting that cites a primary source you can reach.** Follow the link. If the
   article's link is dead or does not say what the article claims, it is not a source.
3. **Reference works** for uncontested background — dates, geography, definitions.

Never treat as a source: content farms, SEO listicles, AI-generated summaries, another
model's output, or a Wikipedia claim whose citation you did not open.

Use `web_search` to find the territory, then `web_extract` on the sources worth reading
in full. Searching alone gives you snippets, and snippets are how facts drift.

## Claim IDs

Every usable fact becomes one claim with one ID. Sequential, zero-padded, stable:
`C001`, `C002`. Never renumber — the drafts cite these.

One claim = one assertion. If a sentence in the pack contains two facts, it is two
claims. Compound claims are how a writer ends up citing `C012` for a fact that `C012`
only half supports.

```json
{
  "id": "C007",
  "text": "The canal was widened to 205 metres at its narrowest point in the 2015 expansion.",
  "sources": ["https://primary.example/expansion-report"],
  "confidence": "high",
  "verified": false,
  "notes": "Report is the canal authority's own — treat as interested but authoritative on dimensions."
}
```

| Field | Rule |
|---|---|
| `id` | `C` + 3+ digits, unique, never reused |
| `text` | One assertion, stated flat, no rhetoric |
| `sources` | ≥1 URL. More than one for anything contested |
| `confidence` | `high` \| `medium` \| `low` |
| `verified` | Set by the verification pass. Starts `false` |
| `notes` | Optional. Source bias, caveats, what the claim does *not* say |

## Confidence

- **`high`** — primary source states it directly. No inference.
- **`medium`** — secondary source, or a reasonable inference from a primary one.
- **`low`** — contested, or resting on a single weak source.

Anything you cannot source at all does not enter the pack as `low`. It does not enter.
`low` means "sourced but disputed", not "vibes".

A `low` claim must be framed in the prose as disputed. The linter warns when one is
cited; the fact auditor rejects if it is stated flat. This is deliberate — contested
facts are an asset. "Nobody agrees on why" is more interesting than false certainty.

## Aim for surplus

Gather roughly **3× more claims than the story can hold**. A 9-beat story might use
25 claims; collect 75.

A writer choosing from an abundant pack writes better than a writer stretching a thin
one. Thin packs are the upstream cause of most slop: with four facts and nine beats to
fill, padding is the only move available, and no amount of review at step 5 fixes a
failure that happened at step 2.

If beats keep failing on prose grounds, check the pack size before blaming the writer.

## The independent verification pass

The pack stops the writer inventing facts. It cannot catch a fact that was already
wrong when gathered — and that error is worse, because everything downstream treats it
as ground truth and the whole review apparatus will wave it through.

So a second agent re-checks the pack, and it must not start from the URLs already
listed. Starting there re-confirms the original mistake.

Delegate with:

- The pack, claim by claim
- Instruction to search independently for corroboration
- Instruction **not** to open the listed sources as a starting point

It returns, per claim:

| Verdict | Action |
|---|---|
| `confirmed` | `verified: true` |
| `contested` | Keep. Drop `confidence` to `low`. Writer must frame as disputed |
| `refuted` | Delete from the pack |
| `unsourceable` | Delete from the pack |

Deleting is correct. A claim nobody can independently reach is not a fact you can build
a story on, however plausible it reads.

`lint_draft.py` hard-fails any citation to a claim with `verified: false`, so the pass
cannot be skipped silently.

## What belongs in the pack beyond facts

Facts alone produce a Wikipedia summary. Also collect:

- **Concrete images** — a number that can be seen, a physical detail, a sensory anchor.
  "400 metres" is a fact; "longer than the Empire State Building is tall" is an image.
- **Direct quotes** — with speaker and date. One good quote outperforms three paraphrases.
- **Scale comparisons** — what makes an abstract number land.
- **Disagreements** — where the sources conflict, and who is on each side.
- **The thing nobody expected** — every good story has one. Look for it explicitly and
  record it, because it is usually the root question's answer.

These are claims too. They get IDs and sources like anything else.
