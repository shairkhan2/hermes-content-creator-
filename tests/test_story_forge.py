"""Tests for the Story Forge validators.

Stdlib + pytest only, no network. The point of these is that the enforcement layer is
itself enforced: a linter that silently stops rejecting is worse than no linter, because
the pipeline keeps reporting approvals.

Run:  python3 -m pytest tests/test_story_forge.py -q
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / "skills" / "story-forge"
CHECK_LEDGER = SKILL / "scripts" / "check_ledger.py"
LINT_DRAFT = SKILL / "scripts" / "lint_draft.py"

VALID_LEDGER = {
    "root_question": "Why did a single ship stopping for six days cost the world $60 billion?",
    "total_beats": 9,
    "target_words": 750,
    "beats": [
        {"n": 1, "job": "Open the root question through one concrete image", "word_budget": 60},
        {"n": 2, "job": "Establish the canal's chokepoint physics", "word_budget": 80},
        {"n": 3, "job": "The grounding itself, minute by minute", "word_budget": 95},
        {"n": 4, "job": "Pay off why it stuck; open why it took so long", "word_budget": 90},
        {"n": 5, "job": "The dredging effort and its limits", "word_budget": 85},
        {"n": 6, "job": "Pay off the delay; open the downstream cost", "word_budget": 90},
        {"n": 7, "job": "Supply chains as a queue, not a pipe", "word_budget": 95},
        {"n": 8, "job": "The tide solution nobody controlled", "word_budget": 80},
        {"n": 9, "job": "Close the root question", "word_budget": 75},
    ],
    "questions": [
        {"id": "Q1", "text": "Why did a single ship stopping for six days cost the world $60 billion?",
         "parent": None, "opened_at": 1, "pays_off_at": 9},
        {"id": "Q2", "text": "What makes this stretch of water impossible to route around?",
         "parent": "Q1", "opened_at": 1, "pays_off_at": 3},
        {"id": "Q3", "text": "How does a ship that size actually get stuck?",
         "parent": "Q1", "opened_at": 2, "pays_off_at": 4},
        {"id": "Q4", "text": "Why did it take six days rather than six hours?",
         "parent": "Q1", "opened_at": 3, "pays_off_at": 6},
        {"id": "Q5", "text": "Why does a six-day pause cost more than six days of trade?",
         "parent": "Q1", "opened_at": 5, "pays_off_at": 8},
        {"id": "Q6", "text": "What finally moved it?",
         "parent": "Q1", "opened_at": 6, "pays_off_at": 9},
    ],
}

PACK = {
    "topic": "Ever Given",
    "claims": [
        {"id": "C001", "text": "The Ever Given grounded on 23 March 2021.",
         "sources": ["https://example.org/a"], "confidence": "high", "verified": True},
        {"id": "C002", "text": "The ship is 400 metres long.",
         "sources": ["https://example.org/b"], "confidence": "high", "verified": True},
        {"id": "C003", "text": "Refloated 29 March 2021 on a spring tide.",
         "sources": ["https://example.org/c"], "confidence": "medium", "verified": False},
        {"id": "C004", "text": "Sources disagree on the total cost.",
         "sources": ["https://example.org/d"], "confidence": "low", "verified": True},
    ],
}

CLEAN_DRAFT = """\
She was four hundred metres of steel [C002], and she turned sideways.

A crosswind came across the beam at forty knots. On a hull stacked nine containers
high, steel stops being a hull and starts being a sail. Her bow swung. Her stern
followed. On 23 March 2021 [C001], the Ever Given wedged herself into both banks of a
channel built with no room to spare.

Every hour, ships behind her dropped anchor and waited.

So the question stops being how she got stuck. Anyone could see how she got stuck. What
nobody could see was why six days of one blocked channel would empty shelves three
continents away.
"""


def run(script, *args):
    proc = subprocess.run(
        [sys.executable, str(script), *[str(a) for a in args]],
        capture_output=True, text=True,
    )
    return proc


def write_ledger(tmp_path, mutate=None, name="ledger.json"):
    data = copy.deepcopy(VALID_LEDGER)
    if mutate:
        mutate(data)
    path = tmp_path / name
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def write_pack(tmp_path, mutate=None):
    data = copy.deepcopy(PACK)
    if mutate:
        mutate(data)
    path = tmp_path / "pack.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def codes(proc):
    """Finding codes from a --json run."""
    payload = json.loads(proc.stdout)
    return {f["code"] for f in payload["errors"]} | {f["code"] for f in payload["warnings"]}


def error_codes(proc):
    return {f["code"] for f in json.loads(proc.stdout)["errors"]}


# --------------------------------------------------------------------------- ledger

def test_valid_ledger_passes(tmp_path):
    proc = run(CHECK_LEDGER, write_ledger(tmp_path))
    assert proc.returncode == 0, proc.stdout
    assert "chain unbroken" in proc.stdout


def test_orphan_question_rejected(tmp_path):
    def mutate(d):
        d["questions"][2].pop("pays_off_at")
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "orphan-question" in error_codes(proc)


def test_instant_payoff_rejected(tmp_path):
    def mutate(d):
        d["questions"][1]["pays_off_at"] = d["questions"][1]["opened_at"]
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "instant-payoff" in error_codes(proc)


def test_multiple_roots_rejected(tmp_path):
    def mutate(d):
        d["questions"][1]["parent"] = None
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "multiple-roots" in error_codes(proc)


def test_root_must_close_last(tmp_path):
    def mutate(d):
        d["questions"][0]["pays_off_at"] = 7
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "root-closes-early" in error_codes(proc)


def test_child_may_not_outlive_parent(tmp_path):
    """`parent` means serves, not follows — the mistake every first ledger makes."""
    def mutate(d):
        d["questions"][3]["parent"] = "Q3"  # Q3 closes at 4, Q4 pays off at 6
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "child-outlives-parent" in error_codes(proc)


def test_parent_cycle_rejected(tmp_path):
    def mutate(d):
        d["questions"][1]["parent"] = "Q3"
        d["questions"][2]["parent"] = "Q2"
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "parent-cycle" in error_codes(proc)


def test_dead_beat_rejected(tmp_path):
    """Every beat before the last must leave a sub-question open."""
    def mutate(d):
        # Close everything by beat 5; beats 5-8 then have nothing open.
        for q in d["questions"][1:]:
            q["opened_at"] = 1
            q["pays_off_at"] = 5
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "dead-beat" in error_codes(proc)


def test_hard_seam_warned(tmp_path):
    """Handoffs where the next question opens only as the previous one closes."""
    def mutate(d):
        d["questions"] = [
            d["questions"][0],
            {"id": "Q2", "text": "First?", "parent": "Q1", "opened_at": 1, "pays_off_at": 4},
            {"id": "Q3", "text": "Second?", "parent": "Q1", "opened_at": 4, "pays_off_at": 9},
        ]
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert "hard-seam" in codes(proc)


def test_overlapping_handoff_has_no_seam(tmp_path):
    """The valid ledger overlaps its questions, so no seam is reported."""
    proc = run(CHECK_LEDGER, write_ledger(tmp_path), "--json")
    assert "hard-seam" not in codes(proc)


def test_beat_without_job_rejected(tmp_path):
    def mutate(d):
        d["beats"][4].pop("job")
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "beat-no-job" in error_codes(proc)


def test_uniform_budgets_warned(tmp_path):
    def mutate(d):
        for b in d["beats"]:
            b["word_budget"] = 83
    proc = run(CHECK_LEDGER, write_ledger(tmp_path, mutate), "--json")
    assert "uniform-budgets" in codes(proc)


def test_bad_json_exits_2(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert run(CHECK_LEDGER, path).returncode == 2


# ---------------------------------------------------------------------------- lint

def test_clean_draft_passes(tmp_path):
    """A linter that fails everything is as useless as one that fails nothing."""
    draft = tmp_path / "clean.md"
    draft.write_text(CLEAN_DRAFT, encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--pack", write_pack(tmp_path), "--budget", 110, "--json")
    assert proc.returncode == 0, proc.stdout
    assert not json.loads(proc.stdout)["errors"]


@pytest.mark.parametrize("phrase", [
    "delve", "tapestry", "it's important to note", "little did they know",
    "but here's the thing", "moreover", "cutting-edge", "seamlessly",
])
def test_banned_phrases_rejected(tmp_path, phrase):
    draft = tmp_path / "d.md"
    draft.write_text(f"The canal mattered. Something {phrase} happened next. Why?\n",
                     encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--json")
    assert proc.returncode == 1
    assert "banned-phrase" in error_codes(proc)


@pytest.mark.parametrize("phrase", [
    "experts say", "studies show", "many believe", "it is said", "sources say",
])
def test_unfalsifiable_attribution_rejected(tmp_path, phrase):
    draft = tmp_path / "d.md"
    draft.write_text(f"Now, {phrase} the canal is vital. Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--json")
    assert proc.returncode == 1
    assert "unfalsifiable" in error_codes(proc)


def test_over_budget_rejected(tmp_path):
    draft = tmp_path / "d.md"
    draft.write_text(" ".join(["word"] * 200) + " Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--budget", 50, "--json")
    assert proc.returncode == 1
    assert "over-budget" in error_codes(proc)


def test_under_budget_warns_but_passes(tmp_path):
    """Short is fine if the beat did its job. Padding to the cap is the failure."""
    draft = tmp_path / "d.md"
    draft.write_text("She turned sideways. Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--budget", 90, "--json")
    assert proc.returncode == 0
    assert "under-budget" in codes(proc)


def test_uncited_factual_assertion_rejected(tmp_path):
    draft = tmp_path / "d.md"
    draft.write_text("The Ever Given grounded on 23 March 2021. What now?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--pack", write_pack(tmp_path), "--json")
    assert proc.returncode == 1
    assert "uncited-claim" in error_codes(proc)


def test_citation_makes_assertion_pass(tmp_path):
    draft = tmp_path / "d.md"
    draft.write_text("The Ever Given grounded on 23 March 2021 [C001]. What now?\n",
                     encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--pack", write_pack(tmp_path), "--json")
    assert "uncited-claim" not in error_codes(proc)


def test_unknown_claim_id_rejected(tmp_path):
    draft = tmp_path / "d.md"
    draft.write_text("A fact [C999]. Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--pack", write_pack(tmp_path), "--no-claims", "--json")
    assert proc.returncode == 1
    assert "unknown-claim" in error_codes(proc)


def test_unverified_claim_rejected(tmp_path):
    """The independent verification pass cannot be skipped silently."""
    draft = tmp_path / "d.md"
    draft.write_text("She refloated days later [C003]. Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--pack", write_pack(tmp_path), "--no-claims", "--json")
    assert proc.returncode == 1
    assert "unverified-claim" in error_codes(proc)


def test_low_confidence_claim_warns(tmp_path):
    draft = tmp_path / "d.md"
    draft.write_text("The cost is disputed [C004]. Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--pack", write_pack(tmp_path), "--no-claims", "--json")
    assert "low-confidence-claim" in codes(proc)


def test_flat_rhythm_warned(tmp_path):
    draft = tmp_path / "d.md"
    sentence = "The ship moved through the narrow channel with care today. "
    draft.write_text(sentence * 6 + "Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--json")
    assert "flat-rhythm" in codes(proc) or "restatement" in codes(proc)


def test_runaway_sentence_warned(tmp_path):
    """Flagged on its own merits, not only when there are enough sentences to compare."""
    draft = tmp_path / "d.md"
    draft.write_text(" ".join(["steel"] * 40) + " landed. Short one. Why?\n", encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--json")
    assert "runaway-sentence" in codes(proc)


def test_interrogative_framing_counts_as_a_question(tmp_path):
    """Narration often poses a question without punctuating it as one."""
    draft = tmp_path / "d.md"
    draft.write_text("She turned sideways. The question is why that emptied shelves.\n",
                     encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--json")
    assert "no-question" not in codes(proc)


def test_beat_with_no_question_warned(tmp_path):
    draft = tmp_path / "d.md"
    draft.write_text("She turned sideways. Tugs arrived. Sand shifted under the bow.\n",
                     encoding="utf-8")
    proc = run(LINT_DRAFT, draft, "--no-claims", "--json")
    assert "no-question" in codes(proc)


def test_missing_file_exits_2(tmp_path):
    assert run(LINT_DRAFT, tmp_path / "nope.md", "--no-claims").returncode == 2
