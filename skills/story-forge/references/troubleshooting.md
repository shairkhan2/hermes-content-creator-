# Troubleshooting

Failure modes of the pipeline itself, and where the actual fix lives. Most quality
problems that show up at step 5 were created at step 2 or step 4.

## Nothing ever passes

**Symptom:** beats burn all three rounds and hit the escape valve repeatedly.

Once is normal. Twice in one story means the fault is upstream, not in the writing.
Check in this order:

1. **Pack size.** Fewer than ~3 usable claims per beat and the writer is stretching.
   Stretching is padding, and every prose auditor will reject padding. Go back to step 2.
2. **Beat job.** Read the beat's `job` in the ledger. If it says something like
   "provide context", it is not a job — it is a hole. Beats need a specific thing to do.
3. **Word budget.** A 60-word cap on a beat carrying three claims cannot be written.
   Rebalance the budgets across beats; totals matter, individual caps do not have to
   be equal.
4. **Auditor calibration.** If one auditor rejects everything while the other three
   approve, read its faults. If they are preferences rather than defects, its prompt
   is over-tuned.

Do not respond by loosening the rules. Fix the input.

## Every auditor approves everything

**Symptom:** first draft, four approvals, every beat, no faults listed.

Something is wrong with the setup. Almost always one of:

- **Auditors share the writer's context.** This is the big one. An auditor that saw the
  writer reason has the justification in context, and every weak line reads as
  intentional. Each auditor needs its own `delegate_task` with only its own inputs.
- **`weakest_element` is empty.** That is a non-response, not an approval. Re-run once
  demanding it; count a second empty return as a rejection.
- **The auditor got the wrong inputs.** A fact auditor without the pack cannot reject
  on citation grounds and will fall back to approving on general impression.

Sanity check the setup by feeding the auditors a deliberately bad draft. If the slop
fixture in this repo's tests passes review, the review is not running.

## The story is accurate, clean, and boring

**Symptom:** everything passes, the linter is silent, and reading it is a chore.

This is the failure the mechanical checks cannot catch, and it is a structure problem,
not a prose problem.

- Re-read the cold reader verdicts. If it never says "I want to keep going", the ledger
  is the issue.
- Check for `dead-beat` conditions the ledger technically satisfies but the prose does
  not — a question nominally open but not *felt* as open. The structure auditor should
  catch this; if it did not, its prompt needs the ledger's open-question list.
- Check the root question. If it can be answered in a sentence, there was never a story
  to tell, and no amount of good writing rescues that. Go back to step 4.

## Word count lands far off target

The total is an outcome of the beat budgets, never something anyone aims at.

- **Consistently under:** beats are doing their jobs in fewer words than budgeted. This
  is fine. Do not pad. Either accept the shorter piece or add a beat with a real job.
- **Consistently over:** `over-budget` errors should have blocked these. If they did
  not, the linter is being run without `--budget`.
- **Wildly off:** check `target_words` in the ledger against the duration table in
  SKILL.md. A words-per-minute mismatch propagates everywhere.

## The linter flags something legitimate

The banned list is deliberately blunt. Occasionally a banned phrase is genuinely the
right word — a story *about* tapestries, a quote containing "experts say".

Handle it by:

1. **Quoting.** Attributed quotes are the writer's evidence, not the writer's voice.
   Put them in the pack as a claim with a speaker, and the fact auditor validates them.
2. **Rewriting.** Nine times out of ten there is a better word, and reaching for the
   exception is itself a signal.

Do not edit `BANNED_PHRASES` to unblock a draft. A linter you edit when it disagrees
with you is a linter that never rejects anything. If a phrase is wrong for the list
across many stories, that is a real change — make it deliberately, not mid-draft.

## `check_ledger.py` rejects a structure that seems right

The two that surprise people:

**`child-outlives-parent`** — almost always a `parent` that should point at the root.
`parent` means *serves*, not *follows*. A question raised by another question's answer
is not that question's child; it is a successor serving whatever is still open. See
`references/loop-ledger.md`.

**`hard-seam`** — a question closes and the only thing carrying across opened in that
same beat. Technically nothing is unresolved, but the story stops and restarts instead
of flowing. The fix is to plant the next question *earlier*, not to delay the current
payoff. Overlap is the mechanism; sequential questions with clean handoffs are exactly
the structure that loses listeners.

## Facts drift between beats

**Symptom:** beat 2 says six days, beat 7 says a week.

Beat-level fact auditors only see one beat, so neither of them can catch this. It is
the continuity check in step 6, and it is why step 6 is not optional even when every
beat passed.

If it happens often, the pack has near-duplicate claims saying slightly different
things. Merge them — one assertion, one ID.

## A source dies mid-project

If `web_extract` cannot reach a claim's source on re-check, the claim is `unsourceable`
and leaves the pack, even if it was verified earlier and even if it is obviously true.

If that guts the story, the topic rests on thinner ground than it appeared to, and the
user should know that. Tell them.

## The user asks to skip the review

They own the call. Say plainly what comes off: without the auditors this is a
single-draft generation with a linter on top, which catches banned phrases and budget
overruns and nothing else. Then do what they asked.

The linter alone is still worth running. It is the cheapest part of the pipeline and
the only part that cannot be talked out of a verdict.
