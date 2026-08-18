#!/usr/bin/env python3
"""Split a story's beat files into TTS clauses, and render both backends' inputs.

Clause granularity is finer than sentence granularity on purpose: shot-forge merges
clauses back up into shots, so the merger needs real boundaries to choose from.
Splitting once, correctly, here beats letting either TTS backend or the shot builder
guess at sentence structure later.

The two TTS backends this pipeline supports get timing two different ways:

  Vertex Cloud TTS   SSML <mark name="b01c01"/> tags; the API echoes back a timepoint
                      per mark name. This script emits the SSML.

  ElevenLabs v3       No SSML marks. Returns character-level alignment for the whole
                      utterance instead. This script emits the plain text actually sent
                      to the API, plus each clause's starting character offset within
                      it — build_voiceover.py later maps offsets to alignment times.

Usage:
    python3 split_clauses.py handoff.json --project-dir <dir> -o clauses.json
    python3 split_clauses.py handoff.json --project-dir <dir> --emit-ssml ssml.xml
    python3 split_clauses.py handoff.json --project-dir <dir> --emit-plain plain.txt --emit-offsets offsets.json

Exit codes: 0 ok, 2 bad input.
"""

import argparse
import json
import re
import sys
from pathlib import Path

CITATION_RE = re.compile(r"\s*\[C\d{3,}\]")  # eats the space before it too
# Split only on a comma/semicolon/em-dash followed by a letter, never a digit — this
# is what keeps "3,000 metres" from being read as a clause boundary.
SUB_CLAUSE_RE = re.compile(r"(?<=[,;—])\s+(?=[A-Za-z])")
SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"'‘“])")

# A sentence longer than this is a candidate for sub-splitting. Below it, splitting
# on commas produces fragments too short to be a useful shot boundary.
SUB_SPLIT_WORD_THRESHOLD = 12
# A sub-clause piece shorter than this gets folded back into its neighbour rather
# than standing alone — "and" or "but" is not a clause.
MIN_CLAUSE_WORDS = 3


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


def strip_markdown(text):
    out = []
    in_fence = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or line.lstrip().startswith(("#", ">")):
            continue
        out.append(line)
    return "\n".join(out)


def clean_beat_text(raw):
    text = CITATION_RE.sub("", strip_markdown(raw))
    return re.sub(r"\s+", " ", text).strip()


def word_count(s):
    return len(re.findall(r"[A-Za-z0-9']+", s))


def split_sentences(text):
    if not text:
        return []
    return [s.strip() for s in SENTENCE_RE.split(text) if s.strip()]


def sub_split(sentence):
    """A long sentence splits further at internal punctuation; short pieces refold."""
    if word_count(sentence) <= SUB_SPLIT_WORD_THRESHOLD:
        return [sentence]

    pieces = [p.strip() for p in SUB_CLAUSE_RE.split(sentence) if p.strip()]
    if len(pieces) <= 1:
        return [sentence]

    merged = []
    for piece in pieces:
        if merged and word_count(piece) < MIN_CLAUSE_WORDS:
            merged[-1] = merged[-1] + " " + piece
        else:
            merged.append(piece)
    # A short remainder at the end reads as a fragment; fold it into its predecessor.
    if len(merged) > 1 and word_count(merged[-1]) < MIN_CLAUSE_WORDS:
        merged[-2] = merged[-2] + " " + merged[-1]
        merged.pop()
    return merged


def split_beat(beat_n, raw_text):
    text = clean_beat_text(raw_text)
    clauses = []
    for sentence in split_sentences(text):
        clauses.extend(sub_split(sentence))
    return [
        {"beat": beat_n, "clause": i + 1, "mark": f"b{beat_n:02d}c{i + 1:02d}", "text": c}
        for i, c in enumerate(clauses)
    ]


def build_clauses(handoff, project_dir):
    beats = handoff.get("beats")
    if not isinstance(beats, list) or not beats:
        die("handoff.json has no 'beats' list")

    all_clauses = []
    for beat in beats:
        n = beat.get("n")
        text_file = beat.get("text_file")
        if not isinstance(n, int) or not text_file:
            die(f"beat entry missing n or text_file: {beat!r}")
        path = Path(project_dir) / text_file
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as exc:
            die(f"cannot read beat text {path}: {exc}")
        clauses = split_beat(n, raw)
        if not clauses:
            die(f"beat {n} produced no clauses — check {path} is not empty")
        all_clauses.extend(clauses)
    return all_clauses


def render_ssml(clauses):
    parts = ['<speak>']
    for c in clauses:
        parts.append(f'<mark name="{c["mark"]}"/>{escape_xml(c["text"])} ')
    parts.append('</speak>')
    return "".join(parts)


def escape_xml(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


def render_plain(clauses):
    """The exact text to send to ElevenLabs, plus each clause's character offset.

    Offsets are computed against this exact string. If the text sent to the API
    differs by even one character, every downstream timestamp lookup is off — so
    this rendering and the offsets are produced together, from the same loop, never
    reconstructed separately later.
    """
    pieces = []
    offsets = []
    cursor = 0
    for i, c in enumerate(clauses):
        offsets.append({"mark": c["mark"], "beat": c["beat"], "clause": c["clause"],
                        "char_offset": cursor, "text": c["text"]})
        pieces.append(c["text"])
        cursor += len(c["text"])
        if i < len(clauses) - 1:
            pieces.append(" ")
            cursor += 1
    return "".join(pieces), offsets


def main():
    ap = argparse.ArgumentParser(description="Split beats into TTS clauses.")
    ap.add_argument("handoff", help="story-forge/tale-forge handoff.json")
    ap.add_argument("--project-dir", required=True,
                    help="directory beat text_file paths are relative to")
    ap.add_argument("-o", "--out", help="write clauses.json here")
    ap.add_argument("--emit-ssml", help="write Vertex SSML here")
    ap.add_argument("--emit-plain", help="write ElevenLabs plain text here")
    ap.add_argument("--emit-offsets", help="write ElevenLabs character offsets here")
    args = ap.parse_args()

    handoff = load_json(args.handoff)
    clauses = build_clauses(handoff, args.project_dir)

    if args.out:
        Path(args.out).write_text(
            json.dumps({"clauses": clauses}, indent=2) + "\n", encoding="utf-8")

    if args.emit_ssml:
        Path(args.emit_ssml).write_text(render_ssml(clauses) + "\n", encoding="utf-8")

    if args.emit_plain or args.emit_offsets:
        plain, offsets = render_plain(clauses)
        if args.emit_plain:
            Path(args.emit_plain).write_text(plain, encoding="utf-8")
        if args.emit_offsets:
            Path(args.emit_offsets).write_text(
                json.dumps({"offsets": offsets}, indent=2) + "\n", encoding="utf-8")

    if not any([args.out, args.emit_ssml, args.emit_plain, args.emit_offsets]):
        print(json.dumps({"clauses": clauses}, indent=2))
    else:
        beats = sorted({c["beat"] for c in clauses})
        print(f"{len(clauses)} clauses across {len(beats)} beats")


if __name__ == "__main__":
    main()
