#!/usr/bin/env python3
"""Validate a Story Forge loop ledger.

The ledger encodes the story's question-chain: which question opens at which beat,
where it pays off, and which question it hangs from. This script turns "do the
questions actually connect?" into pass/fail checks instead of a matter of taste.

Usage:
    python3 check_ledger.py ledger.json
    python3 check_ledger.py ledger.json --json

Exit codes: 0 clean, 1 findings, 2 bad input.
"""

import argparse
import json
import sys
from pathlib import Path

# Checks that are structural violations rather than warnings.
SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"


def finding(code, severity, message, where=None):
    return {"code": code, "severity": severity, "message": message, "where": where}


def load_ledger(path):
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"{path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"{path} must contain a JSON object", file=sys.stderr)
        sys.exit(2)
    return data


def check_shape(data):
    """Structural sanity. Anything failing here makes later checks meaningless."""
    out = []
    for key in ("root_question", "total_beats", "beats", "questions"):
        if key not in data:
            out.append(finding("missing-key", SEVERITY_ERROR, f"ledger has no '{key}'"))
    if out:
        return out

    if not isinstance(data["total_beats"], int) or data["total_beats"] < 2:
        out.append(finding("bad-total-beats", SEVERITY_ERROR,
                           "total_beats must be an integer >= 2"))
    if not isinstance(data["beats"], list) or not data["beats"]:
        out.append(finding("bad-beats", SEVERITY_ERROR, "beats must be a non-empty list"))
    if not isinstance(data["questions"], list) or not data["questions"]:
        out.append(finding("bad-questions", SEVERITY_ERROR,
                           "questions must be a non-empty list"))
    return out


def check_beats(data):
    out = []
    total = data["total_beats"]
    beats = data["beats"]

    if len(beats) != total:
        out.append(finding("beat-count-mismatch", SEVERITY_ERROR,
                           f"total_beats is {total} but {len(beats)} beats are defined"))

    seen = set()
    for i, beat in enumerate(beats):
        where = f"beats[{i}]"
        if not isinstance(beat, dict):
            out.append(finding("bad-beat", SEVERITY_ERROR, "beat must be an object", where))
            continue
        n = beat.get("n")
        if not isinstance(n, int):
            out.append(finding("bad-beat-n", SEVERITY_ERROR, "beat.n must be an integer", where))
            continue
        if n in seen:
            out.append(finding("duplicate-beat", SEVERITY_ERROR, f"beat {n} defined twice", where))
        seen.add(n)
        if not 1 <= n <= total:
            out.append(finding("beat-out-of-range", SEVERITY_ERROR,
                               f"beat {n} outside 1..{total}", where))
        if not beat.get("job"):
            out.append(finding("beat-no-job", SEVERITY_ERROR,
                               f"beat {n} has no 'job' — every beat needs a stated purpose", where))
        budget = beat.get("word_budget")
        if not isinstance(budget, int) or budget <= 0:
            out.append(finding("beat-no-budget", SEVERITY_ERROR,
                               f"beat {n} needs a positive integer word_budget", where))

    missing = sorted(set(range(1, total + 1)) - seen)
    if missing:
        out.append(finding("beats-missing", SEVERITY_ERROR,
                           f"no definition for beat(s): {missing}"))
    return out


def check_questions(data):
    """Every question well-formed, uniquely identified, and hung from a real parent."""
    out = []
    total = data["total_beats"]
    questions = data["questions"]
    by_id = {}

    for i, q in enumerate(questions):
        where = f"questions[{i}]"
        if not isinstance(q, dict):
            out.append(finding("bad-question", SEVERITY_ERROR, "question must be an object", where))
            continue
        qid = q.get("id")
        if not isinstance(qid, str) or not qid:
            out.append(finding("bad-question-id", SEVERITY_ERROR, "question needs a string id", where))
            continue
        if qid in by_id:
            out.append(finding("duplicate-question-id", SEVERITY_ERROR,
                               f"question id {qid} used twice", where))
            continue
        by_id[qid] = q

        if not q.get("text"):
            out.append(finding("question-no-text", SEVERITY_ERROR,
                               f"{qid} has no text", where))
        text = q.get("text") or ""
        if text and not text.rstrip().endswith("?"):
            out.append(finding("question-not-a-question", SEVERITY_WARN,
                               f"{qid} does not read as a question: {text!r}", where))

        opened = q.get("opened_at")
        pays = q.get("pays_off_at")
        if not isinstance(opened, int) or not 1 <= opened <= total:
            out.append(finding("bad-opened-at", SEVERITY_ERROR,
                               f"{qid} opened_at must be an int in 1..{total}", where))
        if not isinstance(pays, int) or not 1 <= pays <= total:
            out.append(finding("orphan-question", SEVERITY_ERROR,
                               f"{qid} never pays off — pays_off_at must be an int in 1..{total}",
                               where))
        if isinstance(opened, int) and isinstance(pays, int) and pays <= opened:
            out.append(finding("instant-payoff", SEVERITY_ERROR,
                               f"{qid} opens at beat {opened} and pays off at {pays} — "
                               "a question answered in the beat that raises it is not a loop",
                               where))

    # Parent links, resolved after all ids are known so forward references are fine.
    for qid, q in by_id.items():
        parent = q.get("parent")
        if parent is None:
            continue
        if parent not in by_id:
            out.append(finding("unknown-parent", SEVERITY_ERROR,
                               f"{qid} hangs from unknown question {parent!r}"))
            continue
        if parent == qid:
            out.append(finding("self-parent", SEVERITY_ERROR, f"{qid} is its own parent"))

    return out, by_id


def check_cycles(by_id):
    out = []
    for qid in by_id:
        seen = set()
        cur = qid
        while cur is not None:
            if cur in seen:
                out.append(finding("parent-cycle", SEVERITY_ERROR,
                                   f"parent chain from {qid} loops back on itself"))
                break
            seen.add(cur)
            node = by_id.get(cur)
            if node is None:
                break
            cur = node.get("parent")
    return out


def check_root(data, by_id):
    """Exactly one root, closing last and closing alone."""
    out = []
    total = data["total_beats"]
    roots = [q for q in by_id.values() if q.get("parent") is None]

    if not roots:
        out.append(finding("no-root", SEVERITY_ERROR,
                           "no question has parent null — the story has no root question"))
        return out, None
    if len(roots) > 1:
        ids = ", ".join(sorted(str(q.get("id")) for q in roots))
        out.append(finding("multiple-roots", SEVERITY_ERROR,
                           f"{len(roots)} root questions ({ids}) — the story splits into "
                           "unconnected threads instead of one chain"))
        return out, None

    root = roots[0]
    if root.get("pays_off_at") != total:
        out.append(finding("root-closes-early", SEVERITY_ERROR,
                           f"root {root.get('id')} pays off at beat {root.get('pays_off_at')}, "
                           f"not the final beat {total}"))
    if root.get("opened_at") != 1:
        out.append(finding("root-opens-late", SEVERITY_WARN,
                           f"root {root.get('id')} opens at beat {root.get('opened_at')} — "
                           "the root question normally opens the story"))

    # A chain of nested questions landing together in the final beat is a cascade:
    # the beat-level question answers its act, the act answers the root. That is the
    # correct shape for long form. What is wrong is *siblings* piling up at the end —
    # several questions with the same parent, none of which set up the others.
    by_parent = {}
    for q in by_id.values():
        if q.get("parent") is not None and q.get("pays_off_at") == total:
            by_parent.setdefault(q["parent"], []).append(str(q.get("id")))
    for parent, siblings in sorted(by_parent.items()):
        if len(siblings) > 1:
            out.append(finding("crowded-ending", SEVERITY_WARN,
                               f"{len(siblings)} sibling questions ({', '.join(sorted(siblings))}) "
                               f"all hang from {parent} and all pay off in the final beat — the "
                               "ending is clearing a backlog instead of landing one answer"))

    declared = (data.get("root_question") or "").strip()
    if declared and root.get("text") and declared != root["text"].strip():
        out.append(finding("root-text-mismatch", SEVERITY_WARN,
                           "root_question does not match the text of the root question"))
    return out, root


def check_nesting(by_id):
    """A child cannot outlive the question that raised it."""
    out = []
    for qid, q in by_id.items():
        parent_id = q.get("parent")
        if parent_id is None or parent_id not in by_id:
            continue
        parent = by_id[parent_id]
        co, cp = q.get("opened_at"), q.get("pays_off_at")
        po, pp = parent.get("opened_at"), parent.get("pays_off_at")
        if not all(isinstance(v, int) for v in (co, cp, po, pp)):
            continue
        if co < po:
            out.append(finding("child-opens-before-parent", SEVERITY_ERROR,
                               f"{qid} opens at beat {co} but its parent {parent_id} "
                               f"only opens at {po}"))
        if cp > pp:
            out.append(finding("child-outlives-parent", SEVERITY_ERROR,
                               f"{qid} pays off at beat {cp}, after its parent {parent_id} "
                               f"closed at {pp}"))
    return out


def check_open_loops(data, by_id, root):
    """The core rule: nothing may be fully resolved before the end."""
    out = []
    total = data["total_beats"]
    root_id = root.get("id") if root else None

    for beat in range(1, total):
        open_subs = [
            q.get("id") for q in by_id.values()
            if q.get("id") != root_id
            and isinstance(q.get("opened_at"), int)
            and isinstance(q.get("pays_off_at"), int)
            and q["opened_at"] <= beat < q["pays_off_at"]
        ]
        if not open_subs:
            out.append(finding("dead-beat", SEVERITY_ERROR,
                               f"beat {beat} ends with no open sub-question — the listener has "
                               "nothing unresolved and leaves here"))

    # A seam is softer than a dead beat: something is open across the handoff, but it
    # only opened in the very beat the previous question closed. The story visibly
    # stops and restarts rather than carrying the listener across.
    for qid, q in by_id.items():
        if qid == root_id:
            continue
        pays = q.get("pays_off_at")
        if not isinstance(pays, int) or pays >= total:
            continue
        carried = [
            other for other in by_id.values()
            if other.get("id") not in (qid, root_id)
            and isinstance(other.get("opened_at"), int)
            and isinstance(other.get("pays_off_at"), int)
            and other["opened_at"] <= pays < other["pays_off_at"]
        ]
        if carried and all(other["opened_at"] == pays for other in carried):
            names = ", ".join(sorted(str(o.get("id")) for o in carried))
            out.append(finding("hard-seam", SEVERITY_WARN,
                               f"{qid} closes at beat {pays} and the only question carrying "
                               f"across ({names}) opens in that same beat — the handoff is "
                               "abrupt. Plant the next question a beat earlier so it overlaps."))
    return out


def check_budget(data):
    out = []
    total_words = sum(b.get("word_budget", 0) for b in data["beats"]
                      if isinstance(b, dict) and isinstance(b.get("word_budget"), int))
    declared = data.get("target_words")
    if isinstance(declared, int) and declared > 0:
        drift = abs(total_words - declared) / declared
        if drift > 0.10:
            out.append(finding("budget-drift", SEVERITY_WARN,
                               f"beat budgets sum to {total_words} words against a target of "
                               f"{declared} ({drift:.0%} off)"))

    budgets = [b["word_budget"] for b in data["beats"]
               if isinstance(b, dict) and isinstance(b.get("word_budget"), int)]
    if budgets and len(set(budgets)) == 1 and len(budgets) > 3:
        out.append(finding("uniform-budgets", SEVERITY_WARN,
                           "every beat has an identical word budget — beats have different "
                           "jobs and should not be the same length"))
    return out


def run_checks(data):
    findings = check_shape(data)
    if findings:
        return findings

    findings += check_beats(data)
    q_findings, by_id = check_questions(data)
    findings += q_findings
    findings += check_cycles(by_id)

    root_findings, root = check_root(data, by_id)
    findings += root_findings
    findings += check_nesting(by_id)
    if root is not None:
        findings += check_open_loops(data, by_id, root)
    findings += check_budget(data)
    return findings


def main():
    parser = argparse.ArgumentParser(description="Validate a Story Forge loop ledger.")
    parser.add_argument("ledger", help="path to ledger JSON")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="emit findings as JSON")
    parser.add_argument("--strict", action="store_true",
                        help="treat warnings as failures")
    args = parser.parse_args()

    data = load_ledger(args.ledger)
    findings = run_checks(data)

    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARN]

    if args.as_json:
        print(json.dumps({
            "ledger": args.ledger,
            "ok": not errors and not (args.strict and warnings),
            "errors": errors,
            "warnings": warnings,
        }, indent=2))
    else:
        for f in errors:
            where = f" ({f['where']})" if f["where"] else ""
            print(f"ERROR  [{f['code']}]{where} {f['message']}")
        for f in warnings:
            where = f" ({f['where']})" if f["where"] else ""
            print(f"WARN   [{f['code']}]{where} {f['message']}")
        if not findings:
            beats = data.get("total_beats", "?")
            qs = len(data.get("questions", []))
            print(f"ledger ok — {qs} questions across {beats} beats, chain unbroken")
        else:
            print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")

    if errors or (args.strict and warnings):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
