"""Tests for Tale Forge — the fiction writer.

Covers what fiction changes: ledgers may leave a question deliberately open, and the
linter swaps citation checks for told-emotion and genre-cliche.

Also asserts the two validators stay byte-identical to story-forge's copies. Each
Hermes skill has to be independently installable, so the scripts are duplicated; this
test is what stops the copies drifting.

Run:  python3 -m pytest tests/test_tale_forge.py -q
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
TALE = ROOT / "skills" / "tale-forge" / "scripts"
STORY = ROOT / "skills" / "story-forge" / "scripts"
CHECK = TALE / "check_ledger.py"
LINT = TALE / "lint_draft.py"

FICTION_LEDGER = {
    "mode": "fiction",
    "root_question": "Why did she stay in the house?",
    "total_beats": 8,
    "beats": [{"n": i, "job": f"beat {i}", "word_budget": 80 + i} for i in range(1, 9)],
    "questions": [
        {"id": "Q1", "text": "Why did she stay in the house?", "parent": None,
         "opened_at": 1, "pays_off_at": 8},
        {"id": "Q2", "text": "Why did the fourth stair stop creaking?", "parent": "Q1",
         "opened_at": 1, "pays_off_at": 4},
        {"id": "Q3", "text": "Who is transmitting on the monitor?", "parent": "Q1",
         "opened_at": 3, "pays_off_at": 6},
        {"id": "Q4", "text": "What was in the room?", "parent": "Q1",
         "opened_at": 5, "unresolved": True,
         "unresolved_reason": "Showing it collapses the dread."},
        {"id": "Q5", "text": "Will she open the door?", "parent": "Q1",
         "opened_at": 6, "pays_off_at": 8},
    ],
}


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *[str(a) for a in args]],
                          capture_output=True, text=True)


def write_ledger(tmp_path, mutate=None):
    d = copy.deepcopy(FICTION_LEDGER)
    if mutate:
        mutate(d)
    p = tmp_path / "ledger.json"
    p.write_text(json.dumps(d), encoding="utf-8")
    return p


def codes(proc):
    d = json.loads(proc.stdout)
    return {f["code"] for f in d["errors"]} | {f["code"] for f in d["warnings"]}


def error_codes(proc):
    return {f["code"] for f in json.loads(proc.stdout)["errors"]}


def lint(tmp_path, text, *extra):
    p = tmp_path / "draft.md"
    p.write_text(text, encoding="utf-8")
    return run(LINT, p, "--mode", "fiction", "--json", *extra)


# ------------------------------------------------------- scripts stay in sync

@pytest.mark.parametrize("name", ["check_ledger.py", "lint_draft.py"])
def test_validators_identical_to_story_forge(name):
    """Skills install independently, so the scripts are duplicated. Don't let them drift."""
    assert (TALE / name).read_bytes() == (STORY / name).read_bytes(), (
        f"{name} has drifted between story-forge and tale-forge")


# ----------------------------------------------------------------- ledger mode

def test_fiction_ledger_with_open_question_passes(tmp_path):
    proc = run(CHECK, write_ledger(tmp_path), "--json")
    assert proc.returncode == 0, proc.stdout
    assert "deliberately-open" in codes(proc)


def test_same_ledger_rejected_in_research_mode(tmp_path):
    """The rule story-forge enforces is still enforced where it belongs."""
    def mutate(d):
        d.pop("mode")
    proc = run(CHECK, write_ledger(tmp_path, mutate), "--mode", "research", "--json")
    assert proc.returncode == 1
    assert "orphan-question" in error_codes(proc)


def test_unresolved_without_reason_rejected(tmp_path):
    """A decision, not an oversight — and the validator can't tell them apart alone."""
    def mutate(d):
        d["questions"][3].pop("unresolved_reason")
    proc = run(CHECK, write_ledger(tmp_path, mutate), "--json")
    assert proc.returncode == 1
    assert "unresolved-without-reason" in error_codes(proc)


def test_embedded_mode_beats_the_flag(tmp_path):
    proc = run(CHECK, write_ledger(tmp_path), "--mode", "research", "--json")
    assert proc.returncode == 0
    assert json.loads(proc.stdout)["mode"] == "fiction"


def test_open_question_keeps_later_beats_alive(tmp_path):
    """An unresolved question stays open forever, so it satisfies no-dead-beat."""
    def mutate(d):
        d["questions"][1]["pays_off_at"] = 3     # Q2 covers beats 1-2
        d["questions"][2]["pays_off_at"] = 4     # Q3 covers beat 3
        d["questions"][3]["opened_at"] = 2       # Q4 is unresolved: covers 2 onward
        d["questions"][4]["opened_at"] = 7
        d["questions"][4]["pays_off_at"] = 8
    proc = run(CHECK, write_ledger(tmp_path, mutate), "--json")
    assert "dead-beat" not in error_codes(proc)


def test_unresolved_root_warns_in_fiction_errors_in_research(tmp_path):
    def mutate(d):
        d["questions"][0].pop("pays_off_at")
        d["questions"][0]["unresolved"] = True
        d["questions"][0]["unresolved_reason"] = "The ending stays ambiguous."
    p = write_ledger(tmp_path, mutate)
    assert "root-unresolved" in codes(run(CHECK, p, "--json"))
    assert run(CHECK, p, "--json").returncode == 0

    d = json.loads(p.read_text())
    d.pop("mode")
    p.write_text(json.dumps(d), encoding="utf-8")
    proc = run(CHECK, p, "--mode", "research", "--json")
    assert proc.returncode == 1
    assert "root-unresolved" in error_codes(proc)


# ------------------------------------------------------------- fiction linter

@pytest.mark.parametrize("line", [
    "She was terrified.",
    "Sarah felt uneasy as she climbed.",
    "The house was eerie.",
    "It filled her with dread.",
    "A sense of foreboding settled over the room.",
    "He grew anxious.",
])
def test_told_emotion_rejected(tmp_path, line):
    """Naming the feeling instead of causing it — fiction's hardest fail."""
    proc = lint(tmp_path, line + " What now?\n")
    assert proc.returncode == 1
    assert "told-emotion" in error_codes(proc)


@pytest.mark.parametrize("line", [
    "A chill ran down her spine.",
    "Her heart pounded.",
    "The silence was deafening.",
    "She wasn't alone.",
    "Or so they thought.",
])
def test_genre_cliche_rejected(tmp_path, line):
    proc = lint(tmp_path, line + " What now?\n")
    assert proc.returncode == 1
    assert "genre-cliche" in error_codes(proc)


def test_clean_horror_prose_passes(tmp_path):
    """A linter that fails everything is as useless as one that fails nothing."""
    text = (
        "The fourth stair had always creaked. Sarah put her weight on it and heard "
        "nothing at all.\n\n"
        "She stood there a while, one foot raised, listening to a house that had "
        "stopped doing the one thing she knew it did. Downstairs the fridge hummed. "
        "Outside, a car passed.\n\n"
        "Up here, nothing.\n\n"
        "She put it down anyway. What else was there to do at two in the morning?\n"
    )
    proc = lint(tmp_path, text, "--budget", "110")
    assert proc.returncode == 0, proc.stdout


def test_fiction_mode_does_not_require_citations(tmp_path):
    """There is no pack to cite, so a factual-looking sentence is just prose."""
    proc = lint(tmp_path, "She was born in 1987 in Grantham Hollow. Why there?\n")
    assert "uncited-claim" not in codes(proc)
    assert proc.returncode == 0, proc.stdout


def test_research_mode_still_requires_citations(tmp_path):
    p = tmp_path / "d.md"
    p.write_text("She was born in 1987 in Grantham Hollow. Why there?\n", encoding="utf-8")
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps({"claims": []}), encoding="utf-8")
    proc = run(LINT, p, "--pack", pack, "--json")
    assert "uncited-claim" in error_codes(proc)


def test_shared_rules_apply_in_both_modes(tmp_path):
    """Banned constructions are slop regardless of genre."""
    proc = lint(tmp_path, "The house was, in today's world, moreover delving. Why?\n")
    assert "banned-phrase" in error_codes(proc)


def test_unfalsifiable_attribution_not_checked_in_fiction(tmp_path):
    """'Legend has it' is a narrator's voice in fiction, not a dodged citation."""
    proc = lint(tmp_path, "Legend has it the house ate them. Did it?\n")
    assert "unfalsifiable" not in codes(proc)
