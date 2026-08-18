#!/usr/bin/env python3
"""Normalize a TTS provider's raw response into the shared voiceover.json contract.

shot-forge consumes one schema regardless of which backend spoke the narration:
marks named b<NN>c<NN> with an exact time_s each. The two backends get there by
different means, and this script is where that difference is resolved — once, in
code, rather than trusted to whoever reads the response next.

  Vertex Cloud TTS   The response already names each mark. This path is a reshape.

  ElevenLabs v3       The response has no marks — only character-level alignment for
                      the whole utterance. This path maps each clause's known
                      character offset (from split_clauses.py's --emit-offsets) to
                      the alignment entry at that offset, and reads its start time.
                      This is the fiddly direction, and the one worth testing hardest.

Usage:
    python3 build_voiceover.py --backend vertex response.json --out voiceover.json --audio-file vo.wav
    python3 build_voiceover.py --backend elevenlabs response.json --offsets offsets.json --out voiceover.json --audio-file vo.mp3

Exit codes: 0 ok, 1 alignment problem, 2 bad input.
"""

import argparse
import json
import sys
from pathlib import Path

EPSILON = 1e-6


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        die(f"cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        die(f"{path} is not valid JSON: {exc}")


def from_vertex(response):
    """Vertex Cloud TTS SSML mark timepoints, already named — a reshape, not a derivation."""
    timepoints = response.get("timepoints")
    if not isinstance(timepoints, list) or not timepoints:
        die("Vertex response has no 'timepoints' list — was the SSML sent with <mark> "
            "tags, and does this voice support markTimingOn?")

    marks = []
    for tp in timepoints:
        name = tp.get("markName")
        t = tp.get("timeSeconds")
        if not name or not isinstance(t, (int, float)):
            die(f"malformed timepoint: {tp!r}")
        marks.append({"name": name, "time_s": float(t)})

    audio_duration = response.get("audioConfig", {}).get("durationSeconds") \
        or response.get("audio_duration_s")
    return marks, audio_duration


def from_elevenlabs(response, offsets):
    """Map each clause's known character offset to the alignment entry there.

    The offsets file and the text actually sent to the API must agree exactly — that
    invariant is enforced by split_clauses.py emitting both from the same loop. If
    they have drifted (edited by hand, or sent through a different render), the
    lengths and characters are checked here rather than trusted.
    """
    alignment = response.get("alignment")
    if not isinstance(alignment, dict):
        die("ElevenLabs response has no 'alignment' object — was this a "
            "with-timestamps endpoint call?")

    chars = alignment.get("characters")
    starts = alignment.get("character_start_times_seconds")
    ends = alignment.get("character_end_times_seconds")
    if not (isinstance(chars, list) and isinstance(starts, list) and len(chars) == len(starts)):
        die("alignment.characters and character_start_times_seconds must be present "
            "and the same length")

    offset_list = offsets.get("offsets")
    if not isinstance(offset_list, list) or not offset_list:
        die("offsets.json has no 'offsets' list")

    marks = []
    problems = []
    for o in offset_list:
        idx = o.get("char_offset")
        name = o.get("mark")
        if not isinstance(idx, int) or not name:
            problems.append(f"malformed offset entry: {o!r}")
            continue
        if idx < 0 or idx >= len(chars):
            problems.append(f"{name}: char_offset {idx} is outside the alignment "
                            f"({len(chars)} characters) — the text sent to the API "
                            "does not match plain.txt")
            continue

        expected = o.get("text", "")
        actual_char = chars[idx]
        if expected and actual_char.strip() and actual_char != expected[0]:
            problems.append(f"{name}: expected clause to start with {expected[0]!r} "
                            f"at offset {idx}, alignment has {actual_char!r} — text "
                            "sent to the API has drifted from plain.txt")
            continue

        marks.append({"name": name, "time_s": float(starts[idx])})

    if problems:
        for p in problems:
            print(f"ERROR  {p}", file=sys.stderr)
        sys.exit(1)

    audio_duration = ends[-1] if ends else None
    return marks, audio_duration


def check_marks(marks, duration_s):
    """Timing has to be strictly increasing, or downstream shot boundaries invert."""
    problems = []
    marks = sorted(marks, key=lambda m: m["time_s"])
    for a, b in zip(marks, marks[1:]):
        if b["time_s"] <= a["time_s"] + EPSILON:
            problems.append(f"{a['name']} ({a['time_s']}s) and {b['name']} "
                            f"({b['time_s']}s) are not strictly increasing")
    if duration_s is not None and marks and marks[-1]["time_s"] >= duration_s:
        problems.append(f"last mark {marks[-1]['name']} at {marks[-1]['time_s']}s is "
                        f"at or after the reported duration {duration_s}s")
    return problems, marks


def attach_text(marks, clauses_path):
    if not clauses_path:
        return marks
    data = load_json(clauses_path)
    text_by_mark = {c["mark"]: c["text"] for c in data.get("clauses", [])}
    for m in marks:
        if m["name"] in text_by_mark:
            m["text"] = text_by_mark[m["name"]]
    return marks


def main():
    ap = argparse.ArgumentParser(description="Normalize a TTS response into voiceover.json.")
    ap.add_argument("response", help="raw provider response JSON")
    ap.add_argument("--backend", required=True, choices=["vertex", "elevenlabs"])
    ap.add_argument("--offsets", help="offsets.json from split_clauses.py (elevenlabs only)")
    ap.add_argument("--clauses", help="clauses.json from split_clauses.py, to attach clause text")
    ap.add_argument("--audio-file", required=True, help="path to the rendered audio file")
    ap.add_argument("--voice", help="voice id/name used, recorded for a matching re-render")
    ap.add_argument("--duration-s", type=float,
                    help="override the audio duration if the response does not report one")
    ap.add_argument("-o", "--out", help="write voiceover.json here (default: stdout)")
    args = ap.parse_args()

    response = load_json(args.response)

    if args.backend == "vertex":
        marks, duration = from_vertex(response)
    else:
        if not args.offsets:
            die("--offsets is required for --backend elevenlabs")
        offsets = load_json(args.offsets)
        marks, duration = from_elevenlabs(response, offsets)

    duration = args.duration_s or duration
    if duration is None:
        die("no duration in the response and none given with --duration-s")

    problems, marks = check_marks(marks, duration)
    if problems:
        for p in problems:
            print(f"ERROR  {p}", file=sys.stderr)
        sys.exit(1)

    marks = attach_text(marks, args.clauses)

    result = {
        "audio_file": args.audio_file,
        "duration_s": round(float(duration), 3),
        "voice": args.voice,
        "backend": args.backend,
        "marks": marks,
    }

    text = json.dumps(result, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"{len(marks)} marks, {result['duration_s']}s, backend={args.backend}")
    else:
        print(text)


if __name__ == "__main__":
    main()
