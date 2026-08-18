#!/usr/bin/env python3
"""Turn a shot list into a backend-agnostic edit manifest, and emit render commands.

The manifest holds edit *decisions* — clip order, transitions, audio mix, output spec.
It says nothing about how they get rendered. That separation is the whole point: the
current backend is ffmpeg, and when OpenCut ships its MCP server the swap is a new
backend reading the same manifest rather than a rewrite.

Backends declare capabilities, and a manifest asking for something the active backend
cannot do is an error at build time rather than a surprise mid-render.

Usage:
    python3 build_edit.py shotlist.json -o edit.json --narration voiceover.wav
    python3 build_edit.py shotlist.json --backend ffmpeg --check
    python3 build_edit.py shotlist.json --emit ffmpeg --clips-dir clips

Exit codes: 0 ok, 1 capability mismatch, 2 bad input.
"""

import argparse
import json
import shlex
import sys
from pathlib import Path

# What each backend can actually render. ffmpeg is what runs today; opencut is
# declared so a manifest can be checked against it before the backend exists.
BACKENDS = {
    "ffmpeg": {
        "available": True,
        # Only what the emitter can actually generate. A capability table that
        # overstates its backend is worse than no table — it moves the failure
        # from build time to render time.
        "transitions": {"cut"},
        "effects": set(),
        "keyframes": False,
        "audio_mix": True,
        "note": "Hard cuts and audio mix, stream-copied. No transitions, no effects.",
    },
    "opencut": {
        "available": False,
        "transitions": {"cut", "dissolve", "wipe", "slide"},
        "effects": {"blur", "glow", "bloom", "color-grade", "mask"},
        "keyframes": True,
        "audio_mix": True,
        "note": "Planned. Waiting on OpenCut's MCP server and headless mode.",
    },
}

DEFAULT_AMBIENCE_DB = -24
DEFAULT_CROSSFADE_MS = 120


def die(msg, code=2):
    print(msg, file=sys.stderr)
    sys.exit(code)


def load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        die(f"cannot read {path}: {exc}")
    except json.JSONDecodeError as exc:
        die(f"{path} is not valid JSON: {exc}")


def build(shotlist, args):
    shots = sorted(shotlist.get("shots", []), key=lambda s: s.get("start_s", 0))
    if not shots:
        die("shot list has no shots")

    clips = []
    for s in shots:
        # A beat head is a hard cut; interior shots chain, which renders as a
        # straight join because consecutive clips already share a frame.
        transition = "cut" if s.get("transition") == "cut" else "chain"
        clips.append({
            "shot": s.get("id"),
            "file": f"{args.clips_dir}/{s.get('id')}.mp4",
            "beat": s.get("beat"),
            "start_s": s.get("start_s"),
            "end_s": s.get("end_s"),
            "duration_s": s.get("duration_s"),
            "transition_in": transition,
            "transition_ms": 0,
            "effects": [],
        })

    return {
        "backend": args.backend,
        "output": {
            "path": args.output_path,
            "width": args.width,
            "height": args.height,
            "fps": args.fps,
            "format": "mp4",
        },
        "audio": {
            "narration": args.narration,
            "ambience_db": args.ambience_db,
            "crossfade_ms": args.crossfade_ms,
        },
        "duration_s": shotlist.get("duration_s"),
        "clip_count": len(clips),
        "clips": clips,
    }


def check_capabilities(edit, backend_name):
    """A manifest asking for what the backend cannot do fails now, not mid-render."""
    backend = BACKENDS.get(backend_name)
    if backend is None:
        die(f"unknown backend {backend_name!r}; known: {sorted(BACKENDS)}")

    problems = []
    if not backend["available"]:
        problems.append(f"backend {backend_name!r} is not available yet — {backend['note']}")

    for clip in edit.get("clips", []):
        t = clip.get("transition_in")
        # "chain" is not a transition, it is the absence of one.
        if t not in backend["transitions"] and t != "chain":
            problems.append(f"{clip.get('shot')}: transition {t!r} unsupported by "
                            f"{backend_name} (has {sorted(backend['transitions'])})")
        for effect in clip.get("effects") or []:
            name = effect.get("type") if isinstance(effect, dict) else effect
            if name not in backend["effects"]:
                problems.append(f"{clip.get('shot')}: effect {name!r} unsupported by "
                                f"{backend_name}")
            if isinstance(effect, dict) and effect.get("keyframes") \
                    and not backend["keyframes"]:
                problems.append(f"{clip.get('shot')}: effect {name!r} is keyframed and "
                                f"{backend_name} cannot keyframe")
    return problems


def emit_ffmpeg(edit):
    """Render commands generated from the manifest, never hand-written.

    Every boundary is a cut, so this is the concat demuxer with a stream copy —
    exact, fast, and no re-encode of the Veo output. Anything richer than a cut is
    rejected by the capability check before reaching here.
    """
    out = edit["output"]
    audio = edit["audio"]
    clips = edit["clips"]
    lines = []
    lines.append("# 1. concat list")
    listing = "\n".join(f"file '{c['file']}'" for c in clips)
    lines.append(f"cat > concat.txt <<'EOF'\n{listing}\nEOF")
    lines.append("")
    lines.append("# 2. join — every boundary is a cut, so this stream-copies:")
    lines.append("#    exact, fast, and no generation loss on the Veo output")
    lines.append("ffmpeg -f concat -safe 0 -i concat.txt -c copy silent.mp4")
    lines.append("")
    lines.append("# 3. narration over the ambience bed")
    if audio.get("narration"):
        af = (f"[0:a]volume={audio['ambience_db']}dB[amb];"
              f"[amb][1:a]amix=inputs=2:duration=first[a]")
        lines.append(
            f"ffmpeg -i silent.mp4 -i {shlex.quote(audio['narration'])} "
            f"-filter_complex \"{af}\" -map 0:v -map \"[a]\" "
            f"-c:v copy {shlex.quote(out['path'])}"
        )
    else:
        lines.append(f"ffmpeg -i silent.mp4 -c copy {shlex.quote(out['path'])}")
    lines.append("")

    lines.append("# 4. verify the render matches the narration")
    lines.append(f"ffprobe -v error -show_entries format=duration -of csv=p=0 "
                 f"{shlex.quote(out['path'])}   # expect ~{edit['duration_s']}")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="Build an edit manifest from a shot list.")
    ap.add_argument("shotlist")
    ap.add_argument("-o", "--out", help="write the manifest here (default: stdout)")
    ap.add_argument("--backend", default="ffmpeg", choices=sorted(BACKENDS))
    ap.add_argument("--clips-dir", default="clips")
    ap.add_argument("--narration", help="narration audio file")
    ap.add_argument("--output-path", default="final.mp4")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=24)
    ap.add_argument("--ambience-db", type=int, default=DEFAULT_AMBIENCE_DB)
    ap.add_argument("--crossfade-ms", type=int, default=DEFAULT_CROSSFADE_MS)
    ap.add_argument("--check", action="store_true",
                    help="validate an existing manifest against the backend and stop")
    ap.add_argument("--emit", choices=["ffmpeg"],
                    help="print render commands for the manifest")
    args = ap.parse_args()

    data = load(args.shotlist)
    # --check accepts either a shot list or an already-built manifest.
    edit = data if "clips" in data else build(data, args)

    problems = check_capabilities(edit, args.backend)
    if problems:
        for p in problems:
            print(f"ERROR  {p}", file=sys.stderr)
        sys.exit(1)

    if args.check:
        b = BACKENDS[args.backend]
        print(f"manifest ok for {args.backend} — {edit['clip_count']} clips, "
              f"{edit['duration_s']}s. {b['note']}")
        sys.exit(0)

    if args.emit:
        print(emit_ffmpeg(edit))
        sys.exit(0)

    text = json.dumps(edit, indent=2)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"{edit['clip_count']} clips, {edit['duration_s']}s, backend={args.backend}")
    else:
        print(text)


if __name__ == "__main__":
    main()
