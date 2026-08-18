"""Tests for the Shot Forge validators.

Stdlib + pytest only, no network, no Vertex calls. These cover the structural
guarantees the render depends on: shots tile the narration exactly, nothing exceeds
the API ceiling, and the keyframe chain actually shares frames.

Run:  python3 -m pytest tests/test_shot_forge.py -q
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / "skills" / "shot-forge"
BUILD = SKILL / "scripts" / "build_shotlist.py"
CHECK = SKILL / "scripts" / "check_shotlist.py"


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *[str(a) for a in args]],
                          capture_output=True, text=True)


def make_vo(beats=4, clauses_per_beat=5, clause_s=2.5, tail_s=2.5):
    marks, t = [], 0.0
    for b in range(1, beats + 1):
        for c in range(1, clauses_per_beat + 1):
            marks.append({"name": f"b{b:02d}c{c:02d}", "time_s": round(t, 3),
                          "text": f"clause {c} of beat {b}"})
            t += clause_s
    return {"audio_file": "vo.wav", "duration_s": round(t - clause_s + tail_s, 3),
            "marks": marks}


def write(tmp_path, name, data):
    p = tmp_path / name
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def build(tmp_path, vo=None, *extra):
    vo_path = write(tmp_path, "vo.json", vo or make_vo())
    out = tmp_path / "shotlist.json"
    proc = run(BUILD, vo_path, "-o", out, *extra)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text())


def check(tmp_path, shotlist, *extra):
    p = write(tmp_path, "sl.json", shotlist)
    return run(CHECK, p, "--json", *extra)


def errors(proc):
    return {f["code"] for f in json.loads(proc.stdout)["errors"]}


def codes(proc):
    d = json.loads(proc.stdout)
    return {f["code"] for f in d["errors"]} | {f["code"] for f in d["warnings"]}


# ---------------------------------------------------------------------- building

def test_build_produces_valid_shotlist(tmp_path):
    sl = build(tmp_path)
    proc = check(tmp_path, sl)
    assert proc.returncode == 0, proc.stdout


def test_no_shot_exceeds_the_api_ceiling(tmp_path):
    """8s is a Veo limit — an over-length shot cannot be rendered at all."""
    sl = build(tmp_path)
    assert sl["shots"], "no shots produced"
    assert max(s["duration_s"] for s in sl["shots"]) <= sl["max_shot_s"] + 1e-6


def test_shots_tile_the_narration_exactly(tmp_path):
    sl = build(tmp_path)
    shots = sorted(sl["shots"], key=lambda s: s["start_s"])
    assert shots[0]["start_s"] == pytest.approx(0.0, abs=0.01)
    for a, b in zip(shots, shots[1:]):
        assert b["start_s"] == pytest.approx(a["end_s"], abs=0.01)
    assert shots[-1]["end_s"] == pytest.approx(sl["duration_s"], abs=0.01)


def test_beats_cut_and_interiors_chain(tmp_path):
    sl = build(tmp_path)
    shots = sorted(sl["shots"], key=lambda s: s["start_s"])
    for s in shots:
        if s["index_in_beat"] == 0:
            assert s["chain_from"] is None and s["transition"] == "cut"
        else:
            assert s["chain_from"] is not None and s["transition"] == "chain"


def test_chained_shots_share_a_frame(tmp_path):
    """Continuity is the shared file, not a similar prompt."""
    sl = build(tmp_path)
    shots = sorted(sl["shots"], key=lambda s: s["start_s"])
    for a, b in zip(shots, shots[1:]):
        if a["beat"] == b["beat"]:
            assert a["end_frame"] == b["start_frame"]
        else:
            assert a["end_frame"] != b["start_frame"]


def test_beat_of_m_shots_has_m_plus_one_frames(tmp_path):
    sl = build(tmp_path)
    for beat in {s["beat"] for s in sl["shots"]}:
        n_shots = sum(1 for s in sl["shots"] if s["beat"] == beat)
        n_frames = sum(1 for f in sl["frames"] if f["beat"] == beat)
        assert n_frames == n_shots + 1


def test_long_clause_is_force_split(tmp_path):
    """A clause over the ceiling cuts mid-sentence; audio is untouched."""
    vo = {"audio_file": "vo.wav", "duration_s": 20.0,
          "marks": [{"name": "b01c01", "time_s": 0.0, "text": "one very long clause"}]}
    sl = build(tmp_path, vo)
    assert any(s["forced_split"] for s in sl["shots"])
    assert max(s["duration_s"] for s in sl["shots"]) <= 8.0 + 1e-6
    assert check(tmp_path, sl).returncode == 0


def test_custom_ceiling_respected(tmp_path):
    sl = build(tmp_path, None, "--max-shot", "5.0")
    assert max(s["duration_s"] for s in sl["shots"]) <= 5.0 + 1e-6


def test_rejects_non_increasing_marks(tmp_path):
    vo = make_vo()
    vo["marks"][3]["time_s"] = vo["marks"][2]["time_s"]
    p = write(tmp_path, "vo.json", vo)
    assert run(BUILD, p).returncode == 2


def test_rejects_bad_mark_names(tmp_path):
    vo = make_vo()
    vo["marks"][0]["name"] = "intro"
    p = write(tmp_path, "vo.json", vo)
    assert run(BUILD, p).returncode == 2


def test_rejects_missing_duration(tmp_path):
    vo = make_vo()
    del vo["duration_s"]
    p = write(tmp_path, "vo.json", vo)
    assert run(BUILD, p).returncode == 2


# --------------------------------------------------------------------- checking

def test_over_ceiling_is_an_error(tmp_path):
    sl = build(tmp_path)
    sl["shots"][2]["duration_s"] = 11.0
    sl["shots"][2]["end_s"] = sl["shots"][2]["start_s"] + 11.0
    assert "over-ceiling" in errors(check(tmp_path, sl))


def test_timeline_gap_detected(tmp_path):
    sl = build(tmp_path)
    sl["shots"][3]["start_s"] += 3.0
    assert "timeline-gap" in errors(check(tmp_path, sl))


def test_timeline_overlap_detected(tmp_path):
    sl = build(tmp_path)
    sl["shots"][3]["start_s"] -= 1.5
    assert "timeline-overlap" in errors(check(tmp_path, sl))


def test_chain_across_beats_rejected(tmp_path):
    sl = build(tmp_path)
    head = next(s for s in sl["shots"] if s["index_in_beat"] == 0 and s["beat"] > 1)
    head["chain_from"] = "s0001"
    assert "chain-across-beats" in errors(check(tmp_path, sl))


def test_cut_inside_a_beat_rejected(tmp_path):
    sl = build(tmp_path)
    interior = next(s for s in sl["shots"] if s["index_in_beat"] > 0)
    interior["chain_from"] = None
    assert "broken-chain" in errors(check(tmp_path, sl))


def test_chained_shots_not_sharing_a_frame_rejected(tmp_path):
    sl = build(tmp_path)
    interior = next(s for s in sl["shots"] if s["index_in_beat"] > 0)
    interior["start_frame"] = sl["frames"][0]["id"]
    assert "chain-frame-mismatch" in errors(check(tmp_path, sl))


def test_degenerate_shot_rejected(tmp_path):
    sl = build(tmp_path)
    sl["shots"][0]["end_frame"] = sl["shots"][0]["start_frame"]
    assert "degenerate-shot" in errors(check(tmp_path, sl))


def test_unknown_frame_rejected(tmp_path):
    sl = build(tmp_path)
    sl["shots"][1]["end_frame"] = "does-not-exist"
    assert "unknown-frame" in errors(check(tmp_path, sl))


def test_motion_required_only_under_flag(tmp_path):
    sl = build(tmp_path)
    assert check(tmp_path, sl).returncode == 0
    assert "no-motion" in codes(check(tmp_path, sl))
    assert check(tmp_path, sl, "--require-motion").returncode == 1


def test_bad_motion_value_always_rejected(tmp_path):
    sl = build(tmp_path)
    sl["shots"][0]["motion"] = "zoom-and-pan-and-fade"
    assert "bad-motion" in errors(check(tmp_path, sl))


def test_prompts_required_only_under_flag(tmp_path):
    sl = build(tmp_path)
    assert check(tmp_path, sl).returncode == 0
    assert check(tmp_path, sl, "--require-prompts").returncode == 1


def test_fully_filled_shotlist_passes_strictest_check(tmp_path):
    """The state a render is actually allowed to start from."""
    sl = build(tmp_path)
    for s in sl["shots"]:
        s["motion"] = "camera"
        s["prompt"] = "slow push in"
    for f in sl["frames"]:
        f["prompt"] = "style | subject | composition"
    proc = check(tmp_path, sl, "--require-prompts", "--require-motion")
    assert proc.returncode == 0, proc.stdout


def test_large_render_warns(tmp_path):
    """A 30-minute story is hundreds of Veo calls — never let that be a surprise."""
    sl = build(tmp_path, make_vo(beats=40, clauses_per_beat=20))
    assert "large-render" in codes(check(tmp_path, sl))


def test_bad_json_exits_2(tmp_path):
    p = tmp_path / "broken.json"
    p.write_text("{not json", encoding="utf-8")
    assert run(CHECK, p).returncode == 2


# --------------------------------------------------------------- render backends

EDIT = SKILL / "scripts" / "build_edit.py"


def build_edit(tmp_path, shotlist, *extra):
    sl = write(tmp_path, "sl.json", shotlist)
    out = tmp_path / "edit.json"
    proc = run(EDIT, sl, "-o", out, "--narration", "vo.wav", *extra)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text())


def test_edit_manifest_builds_from_shotlist(tmp_path):
    edit = build_edit(tmp_path, build(tmp_path))
    assert edit["backend"] == "ffmpeg"
    assert edit["clip_count"] == len(edit["clips"])
    assert all(c["file"].endswith(".mp4") for c in edit["clips"])


def test_beat_heads_are_cuts_interiors_chain(tmp_path):
    sl = build(tmp_path)
    edit = build_edit(tmp_path, sl)
    by_shot = {s["id"]: s for s in sl["shots"]}
    for clip in edit["clips"]:
        expected = "cut" if by_shot[clip["shot"]]["index_in_beat"] == 0 else "chain"
        assert clip["transition_in"] == expected


def test_ffmpeg_rejects_effects_it_cannot_render(tmp_path):
    """The capability gate fails at build time, not mid-render."""
    edit = build_edit(tmp_path, build(tmp_path))
    edit["clips"][1]["effects"] = [{"type": "blur", "keyframes": [{"t": 0, "v": 0}]}]
    p = write(tmp_path, "e.json", edit)
    proc = run(EDIT, p, "--check")
    assert proc.returncode == 1
    assert "blur" in proc.stderr and "keyframe" in proc.stderr


def test_ffmpeg_rejects_transitions_the_emitter_cannot_generate(tmp_path):
    """The table lists only what the emitter builds — dissolve is not in it."""
    edit = build_edit(tmp_path, build(tmp_path))
    edit["clips"][2]["transition_in"] = "dissolve"
    p = write(tmp_path, "e.json", edit)
    proc = run(EDIT, p, "--check")
    assert proc.returncode == 1
    assert "dissolve" in proc.stderr


def test_opencut_backend_declared_but_unavailable(tmp_path):
    edit = build_edit(tmp_path, build(tmp_path))
    p = write(tmp_path, "e.json", edit)
    proc = run(EDIT, p, "--check", "--backend", "opencut")
    assert proc.returncode == 1
    assert "not available yet" in proc.stderr


def test_clean_manifest_passes_ffmpeg_check(tmp_path):
    edit = build_edit(tmp_path, build(tmp_path))
    p = write(tmp_path, "e.json", edit)
    proc = run(EDIT, p, "--check")
    assert proc.returncode == 0, proc.stderr


def test_emitted_commands_are_valid_shell(tmp_path):
    """Generated, never hand-written — that is what keeps the backend swappable."""
    edit = build_edit(tmp_path, build(tmp_path))
    p = write(tmp_path, "e.json", edit)
    proc = run(EDIT, p, "--emit", "ffmpeg")
    assert proc.returncode == 0
    script = tmp_path / "cmds.sh"
    script.write_text(proc.stdout, encoding="utf-8")
    assert subprocess.run(["bash", "-n", str(script)]).returncode == 0
    assert "-c copy" in proc.stdout           # stream copy, no re-encode
    assert "amix" in proc.stdout              # narration over ambience
    assert "ffprobe" in proc.stdout           # verification step


def test_emitted_concat_lists_every_clip_in_order(tmp_path):
    edit = build_edit(tmp_path, build(tmp_path))
    p = write(tmp_path, "e.json", edit)
    out = run(EDIT, p, "--emit", "ffmpeg").stdout
    listed = [l.split("'")[1] for l in out.splitlines() if l.startswith("file '")]
    assert listed == [c["file"] for c in edit["clips"]]


def test_unknown_backend_rejected(tmp_path):
    edit = build_edit(tmp_path, build(tmp_path))
    p = write(tmp_path, "e.json", edit)
    assert run(EDIT, p, "--check", "--backend", "premiere").returncode == 2
