#!/usr/bin/env python3
"""Turn voiceover timepoints into a Veo-ready shot list.

The narration is the spine. Shot boundaries are chosen against real audio
durations, never estimates, so nothing downstream drifts.

Clauses are marked fine-grained during TTS; this merges them into shots that fit
Veo's 8-second ceiling, chains keyframes within a beat so consecutive clips share
a frame, and cuts at beat boundaries so the edit lands on the story's question chain.

Usage:
    python3 build_shotlist.py voiceover.json --handoff handoff.json -o shotlist.json
    python3 build_shotlist.py voiceover.json --max-shot 8.0 --min-shot 1.5

Exit codes: 0 ok, 2 bad input.
"""

import argparse
import json
import math
import re
import sys
from pathlib import Path

MARK_RE = re.compile(r"^b(\d+)c(\d+)$")

# Veo 3.1 generates at most 8 seconds per call. This is a hard API ceiling, not a
# style preference — a shot over it cannot be rendered.
DEFAULT_MAX_SHOT_S = 8.0
# Below about a second and a half a clip reads as a flicker rather than a shot.
DEFAULT_MIN_SHOT_S = 1.5


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(2)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        die(f"cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        die(f"{path} is not valid JSON: {exc}")


def parse_marks(vo):
    """Marks carry the start of each clause; a clause ends where the next begins."""
    marks = vo.get("marks")
    if not isinstance(marks, list) or not marks:
        die("voiceover.json has no 'marks' list")
    duration = vo.get("duration_s")
    if not isinstance(duration, (int, float)) or duration <= 0:
        die("voiceover.json needs a positive 'duration_s'")

    clauses = []
    for m in marks:
        if not isinstance(m, dict):
            die(f"mark is not an object: {m!r}")
        name = m.get("name", "")
        match = MARK_RE.match(str(name))
        if not match:
            die(f"mark name {name!r} does not match b<NN>c<NN>")
        t = m.get("time_s")
        if not isinstance(t, (int, float)):
            die(f"mark {name} has no numeric time_s")
        clauses.append({
            "beat": int(match.group(1)),
            "clause": int(match.group(2)),
            "mark": name,
            "start_s": float(t),
            "text": m.get("text", ""),
        })

    clauses.sort(key=lambda c: c["start_s"])
    for i, c in enumerate(clauses):
        c["end_s"] = clauses[i + 1]["start_s"] if i + 1 < len(clauses) else float(duration)
        if c["end_s"] <= c["start_s"]:
            die(f"mark {c['mark']} has non-positive duration "
                f"({c['start_s']} -> {c['end_s']}) — marks must be strictly increasing")
    return clauses, float(duration)


def split_long_clause(clause, max_shot_s):
    """A clause longer than the API ceiling has to be cut mid-sentence.

    The audio is not touched; only the visual is cut. Flagged so the shot list
    records that this boundary was forced rather than chosen.
    """
    span = clause["end_s"] - clause["start_s"]
    parts = math.ceil(span / max_shot_s)
    step = span / parts
    out = []
    for i in range(parts):
        out.append({
            "clauses": [clause["mark"]],
            "start_s": clause["start_s"] + i * step,
            "end_s": clause["start_s"] + (i + 1) * step if i < parts - 1 else clause["end_s"],
            "text": clause["text"] if i == 0 else "",
            "forced_split": True,
        })
    return out


def group_beat(clauses, max_shot_s, min_shot_s):
    """Greedily merge consecutive clauses up to the ceiling, never across beats."""
    groups = []
    current = None

    for c in clauses:
        span = c["end_s"] - c["start_s"]
        if span > max_shot_s:
            if current:
                groups.append(current)
                current = None
            groups.extend(split_long_clause(c, max_shot_s))
            continue

        if current and (c["end_s"] - current["start_s"]) <= max_shot_s:
            current["clauses"].append(c["mark"])
            current["end_s"] = c["end_s"]
            current["text"] = (current["text"] + " " + c["text"]).strip()
        else:
            if current:
                groups.append(current)
            current = {
                "clauses": [c["mark"]],
                "start_s": c["start_s"],
                "end_s": c["end_s"],
                "text": c["text"],
                "forced_split": False,
            }
    if current:
        groups.append(current)

    # A runt at the end of a beat reads as a flicker. Fold it back if there is room.
    if len(groups) > 1:
        last = groups[-1]
        if (last["end_s"] - last["start_s"]) < min_shot_s:
            prev = groups[-2]
            if (last["end_s"] - prev["start_s"]) <= max_shot_s:
                prev["clauses"].extend(last["clauses"])
                prev["end_s"] = last["end_s"]
                prev["text"] = (prev["text"] + " " + last["text"]).strip()
                groups.pop()
    return groups


def build(clauses, duration, max_shot_s, min_shot_s):
    by_beat = {}
    for c in clauses:
        by_beat.setdefault(c["beat"], []).append(c)

    shots = []
    frames = []
    shot_n = 0

    for beat in sorted(by_beat):
        groups = group_beat(by_beat[beat], max_shot_s, min_shot_s)

        # One more frame than shots: consecutive shots in a beat share a frame, so a
        # beat of m shots needs m+1 keyframes. Sharing is what makes the chain
        # continuous — the end of one clip IS the start of the next.
        frame_ids = [f"f{beat:02d}_{i:02d}" for i in range(len(groups) + 1)]
        for i, fid in enumerate(frame_ids):
            frames.append({
                "id": fid,
                "beat": beat,
                "role": "open" if i == 0 else ("close" if i == len(groups) else "hinge"),
                "at_s": groups[i]["start_s"] if i < len(groups) else groups[-1]["end_s"],
            })

        for i, g in enumerate(groups):
            shot_n += 1
            shots.append({
                "id": f"s{shot_n:04d}",
                "beat": beat,
                "index_in_beat": i,
                "start_s": round(g["start_s"], 3),
                "end_s": round(g["end_s"], 3),
                "duration_s": round(g["end_s"] - g["start_s"], 3),
                "clauses": g["clauses"],
                "narration": g["text"],
                "start_frame": frame_ids[i],
                "end_frame": frame_ids[i + 1],
                # Null at the head of a beat: that is the hard cut, landing on the
                # point where the story's question chain turns.
                "chain_from": None if i == 0 else f"s{shot_n - 1:04d}",
                "transition": "cut" if i == 0 else "chain",
                "forced_split": g["forced_split"],
                "motion": None,
                "prompt": None,
            })

    return {
        "max_shot_s": max_shot_s,
        "min_shot_s": min_shot_s,
        "duration_s": round(duration, 3),
        "shot_count": len(shots),
        "frame_count": len(frames),
        "frames": frames,
        "shots": shots,
    }


def main():
    ap = argparse.ArgumentParser(description="Build a shot list from voiceover timepoints.")
    ap.add_argument("voiceover", help="voiceover.json with marks and duration_s")
    ap.add_argument("--handoff", help="story-forge handoff.json (records provenance)")
    ap.add_argument("-o", "--out", help="write shot list here (default: stdout)")
    ap.add_argument("--max-shot", type=float, default=DEFAULT_MAX_SHOT_S,
                    help=f"API ceiling per clip (default {DEFAULT_MAX_SHOT_S})")
    ap.add_argument("--min-shot", type=float, default=DEFAULT_MIN_SHOT_S,
                    help=f"below this a clip reads as a flicker (default {DEFAULT_MIN_SHOT_S})")
    args = ap.parse_args()

    if args.max_shot <= 0 or args.min_shot <= 0 or args.min_shot >= args.max_shot:
        die("--min-shot must be positive and below --max-shot")

    vo = load_json(args.voiceover)
    clauses, duration = parse_marks(vo)
    result = build(clauses, duration, args.max_shot, args.min_shot)

    result["audio_file"] = vo.get("audio_file")
    if args.handoff:
        handoff = load_json(args.handoff)
        result["title"] = handoff.get("title")
        result["root_question"] = handoff.get("root_question")

    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        forced = sum(1 for s in result["shots"] if s["forced_split"])
        print(f"{result['shot_count']} shots, {result['frame_count']} keyframes, "
              f"{result['duration_s']}s"
              + (f", {forced} forced split(s)" if forced else ""))
    else:
        print(text)


if __name__ == "__main__":
    main()
