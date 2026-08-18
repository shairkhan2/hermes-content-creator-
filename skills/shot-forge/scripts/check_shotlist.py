#!/usr/bin/env python3
"""Validate a shot list before anything is rendered.

Every finding here is cheap. The same fault caught after generation costs hundreds
of Veo calls, so this runs before the first frame exists and again after prompts
are filled in.

Usage:
    python3 check_shotlist.py shotlist.json
    python3 check_shotlist.py shotlist.json --json --require-prompts

Exit codes: 0 clean, 1 findings, 2 bad input.
"""

import argparse
import json
import sys
from pathlib import Path

SEVERITY_ERROR = "error"
SEVERITY_WARN = "warn"

# One change per shot. Start and end frames too similar and the model produces
# nothing; too different and it interpolates through mush.
VALID_MOTION = {"camera", "subject", "reveal", "hold"}
EPSILON = 0.05  # seconds of float slack when comparing timeline boundaries
# Per-code cap on printed examples; the rest are summarised as a count.
MAX_EXAMPLES_PER_CODE = 3


def finding(code, severity, message, where=None):
    return {"code": code, "severity": severity, "message": message, "where": where}


def load(path):
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"cannot read {path}: {exc}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"{path} is not valid JSON: {exc}", file=sys.stderr)
        sys.exit(2)
    if not isinstance(data, dict):
        print(f"{path} must contain a JSON object", file=sys.stderr)
        sys.exit(2)
    return data


def check_shape(d):
    out = []
    for key in ("shots", "frames", "duration_s", "max_shot_s"):
        if key not in d:
            out.append(finding("missing-key", SEVERITY_ERROR, f"shot list has no '{key}'"))
    if out:
        return out
    if not isinstance(d["shots"], list) or not d["shots"]:
        out.append(finding("no-shots", SEVERITY_ERROR, "shots must be a non-empty list"))
    if not isinstance(d["frames"], list) or not d["frames"]:
        out.append(finding("no-frames", SEVERITY_ERROR, "frames must be a non-empty list"))
    return out


def check_durations(d):
    """The API ceiling is not negotiable — an over-length shot simply cannot render."""
    out = []
    ceiling = d["max_shot_s"]
    floor = d.get("min_shot_s", 0)
    for s in d["shots"]:
        sid = s.get("id", "?")
        dur = s.get("duration_s")
        if not isinstance(dur, (int, float)):
            out.append(finding("bad-duration", SEVERITY_ERROR,
                               f"{sid} has no numeric duration_s", sid))
            continue
        if dur > ceiling + EPSILON:
            out.append(finding("over-ceiling", SEVERITY_ERROR,
                               f"{sid} is {dur}s, above the {ceiling}s API ceiling — "
                               "Veo cannot render this in one call", sid))
        if dur <= 0:
            out.append(finding("bad-duration", SEVERITY_ERROR,
                               f"{sid} has non-positive duration", sid))
        elif floor and dur < floor - EPSILON:
            out.append(finding("flicker", SEVERITY_WARN,
                               f"{sid} is {dur}s, below {floor}s — reads as a flicker "
                               "rather than a shot", sid))
    return out


def check_timeline(d):
    """Shots must tile the narration exactly: no gaps, no overlaps, no drift."""
    out = []
    shots = sorted(d["shots"], key=lambda s: s.get("start_s", 0))

    first = shots[0].get("start_s")
    if isinstance(first, (int, float)) and first > EPSILON:
        out.append(finding("timeline-gap", SEVERITY_ERROR,
                           f"first shot starts at {first}s — narration from 0s is uncovered"))

    for a, b in zip(shots, shots[1:]):
        end, start = a.get("end_s"), b.get("start_s")
        if not isinstance(end, (int, float)) or not isinstance(start, (int, float)):
            continue
        delta = start - end
        if delta > EPSILON:
            out.append(finding("timeline-gap", SEVERITY_ERROR,
                               f"{delta:.2f}s of narration between {a.get('id')} and "
                               f"{b.get('id')} has no shot covering it"))
        elif delta < -EPSILON:
            out.append(finding("timeline-overlap", SEVERITY_ERROR,
                               f"{a.get('id')} and {b.get('id')} overlap by {-delta:.2f}s"))

    last = shots[-1].get("end_s")
    total = d.get("duration_s")
    if isinstance(last, (int, float)) and isinstance(total, (int, float)):
        if abs(last - total) > EPSILON:
            out.append(finding("timeline-short", SEVERITY_ERROR,
                               f"shots end at {last}s but the narration runs to {total}s"))
    return out


def check_chain(d):
    """Within a beat, consecutive shots share a frame. That shared frame IS the
    continuity — if the ids do not line up, the chain is decorative."""
    out = []
    frame_ids = {f.get("id") for f in d["frames"] if isinstance(f, dict)}
    shots = sorted(d["shots"], key=lambda s: s.get("start_s", 0))
    by_id = {s.get("id"): s for s in shots}

    for s in shots:
        sid = s.get("id", "?")
        for key in ("start_frame", "end_frame"):
            fid = s.get(key)
            if fid not in frame_ids:
                out.append(finding("unknown-frame", SEVERITY_ERROR,
                                   f"{sid}.{key} references unknown frame {fid!r}", sid))
        if s.get("start_frame") == s.get("end_frame"):
            out.append(finding("degenerate-shot", SEVERITY_ERROR,
                               f"{sid} starts and ends on the same frame — nothing to "
                               "interpolate", sid))

    for a, b in zip(shots, shots[1:]):
        same_beat = a.get("beat") == b.get("beat")
        chained = b.get("chain_from") is not None

        if same_beat and not chained:
            out.append(finding("broken-chain", SEVERITY_ERROR,
                               f"{b.get('id')} is mid-beat but does not chain from "
                               f"{a.get('id')} — this is a cut inside a beat"))
        if not same_beat and chained:
            out.append(finding("chain-across-beats", SEVERITY_ERROR,
                               f"{b.get('id')} chains across a beat boundary — beats must "
                               "hard-cut so the edit lands on the question chain"))
        if same_beat and chained:
            if b.get("chain_from") != a.get("id"):
                out.append(finding("chain-mismatch", SEVERITY_ERROR,
                                   f"{b.get('id')}.chain_from is {b.get('chain_from')!r}, "
                                   f"expected {a.get('id')!r}"))
            if a.get("end_frame") != b.get("start_frame"):
                out.append(finding("chain-frame-mismatch", SEVERITY_ERROR,
                                   f"{a.get('id')} ends on {a.get('end_frame')} but "
                                   f"{b.get('id')} starts on {b.get('start_frame')} — "
                                   "chained shots must share the frame"))

    for s in shots:
        cf = s.get("chain_from")
        if cf is not None and cf not in by_id:
            out.append(finding("unknown-chain-source", SEVERITY_ERROR,
                               f"{s.get('id')}.chain_from references unknown shot {cf!r}"))
    return out


def check_frame_reuse(d):
    """A hinge frame is used exactly twice; ends of a beat exactly once."""
    out = []
    usage = {}
    for s in d["shots"]:
        for key in ("start_frame", "end_frame"):
            fid = s.get(key)
            if fid:
                usage.setdefault(fid, []).append(s.get("id"))
    for f in d["frames"]:
        fid = f.get("id")
        users = usage.get(fid, [])
        if not users:
            out.append(finding("orphan-frame", SEVERITY_WARN,
                               f"frame {fid} is generated but never used by a shot", fid))
        elif len(users) > 2:
            out.append(finding("frame-overused", SEVERITY_ERROR,
                               f"frame {fid} is used by {len(users)} shots "
                               f"({', '.join(str(u) for u in users)})", fid))
    return out


def check_motion(d, require):
    """One change per shot, declared. Two people trying to change everything at once
    is where most bad keyframe video comes from."""
    out = []
    for s in d["shots"]:
        sid = s.get("id", "?")
        motion = s.get("motion")
        if motion is None:
            severity = SEVERITY_ERROR if require else SEVERITY_WARN
            out.append(finding("no-motion", severity,
                               f"{sid} has no declared motion — one of "
                               f"{sorted(VALID_MOTION)}", sid))
        elif motion not in VALID_MOTION:
            out.append(finding("bad-motion", SEVERITY_ERROR,
                               f"{sid}.motion is {motion!r}, not one of "
                               f"{sorted(VALID_MOTION)}", sid))
    return out


def check_prompts(d, require):
    out = []
    if not require:
        return out
    for s in d["shots"]:
        if not s.get("prompt"):
            out.append(finding("no-prompt", SEVERITY_ERROR,
                               f"{s.get('id')} has no prompt", s.get("id")))
    for f in d["frames"]:
        if not f.get("prompt"):
            out.append(finding("no-frame-prompt", SEVERITY_ERROR,
                               f"frame {f.get('id')} has no prompt", f.get("id")))
    return out


def check_scale(d):
    """Volume is not a fault, but it should never be a surprise."""
    out = []
    shots, frames = len(d["shots"]), len(d["frames"])
    if shots > 150:
        out.append(finding("large-render", SEVERITY_WARN,
                           f"{shots} Veo calls and {frames} Imagen calls — run in the "
                           "background with notify_on_complete and confirm the budget "
                           "with the user first"))
    return out


def run_checks(d, require_prompts, require_motion):
    findings = check_shape(d)
    if findings:
        return findings
    findings += check_durations(d)
    findings += check_timeline(d)
    findings += check_chain(d)
    findings += check_frame_reuse(d)
    findings += check_motion(d, require_motion)
    findings += check_prompts(d, require_prompts)
    findings += check_scale(d)
    return findings


def main():
    ap = argparse.ArgumentParser(description="Validate a shot list before rendering.")
    ap.add_argument("shotlist")
    ap.add_argument("--json", action="store_true", dest="as_json")
    ap.add_argument("--strict", action="store_true", help="treat warnings as failures")
    ap.add_argument("--require-prompts", action="store_true",
                    help="fail when any shot or frame prompt is unfilled")
    ap.add_argument("--require-motion", action="store_true",
                    help="fail when any shot has no declared motion")
    args = ap.parse_args()

    d = load(args.shotlist)
    findings = run_checks(d, args.require_prompts, args.require_motion)
    errors = [f for f in findings if f["severity"] == SEVERITY_ERROR]
    warnings = [f for f in findings if f["severity"] == SEVERITY_WARN]

    if args.as_json:
        print(json.dumps({
            "shotlist": args.shotlist,
            "ok": not errors and not (args.strict and warnings),
            "errors": errors,
            "warnings": warnings,
        }, indent=2))
    else:
        # Findings repeat per shot, and a few hundred identical lines is output
        # nobody reads. Collapse by code, showing examples and a count.
        for group in (errors, warnings):
            by_code = {}
            for f in group:
                by_code.setdefault(f["code"], []).append(f)
            for code, items in by_code.items():
                tag = "ERROR " if items[0]["severity"] == SEVERITY_ERROR else "WARN  "
                for f in items[:MAX_EXAMPLES_PER_CODE]:
                    where = f" ({f['where']})" if f.get("where") else ""
                    print(f"{tag} [{code}]{where} {f['message']}")
                if len(items) > MAX_EXAMPLES_PER_CODE:
                    rest = len(items) - MAX_EXAMPLES_PER_CODE
                    subjects = [str(f.get("where")) for f in items if f.get("where")]
                    tail = f" ({', '.join(subjects[MAX_EXAMPLES_PER_CODE:][:8])}"
                    tail += ", ...)" if rest > 8 else ")"
                    print(f"{tag} [{code}] ... and {rest} more{tail if subjects else ''}")
        if not findings:
            print(f"shot list ok — {len(d['shots'])} shots, {len(d['frames'])} frames, "
                  f"{d['duration_s']}s, chain intact")
        else:
            print(f"\n{len(errors)} error(s), {len(warnings)} warning(s)")

    sys.exit(1 if errors or (args.strict and warnings) else 0)


if __name__ == "__main__":
    main()
