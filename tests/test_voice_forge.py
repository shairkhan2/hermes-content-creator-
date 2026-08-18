"""Tests for Voice Forge — the clause splitter and TTS response normalizer.

Stdlib + pytest only, no network. These cover the part most likely to fail silently:
turning ElevenLabs' character-level alignment into clause timing depends on an offset
computed elsewhere staying in sync with the exact text sent to the API. If it drifts,
nothing looks obviously wrong downstream — it just produces a plausible, wrong shot
list. These tests exist to make that drift loud instead.

Run:  python3 -m pytest tests/test_voice_forge.py -q
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

SKILL = Path(__file__).resolve().parents[1] / "skills" / "voice-forge"
SPLIT = SKILL / "scripts" / "split_clauses.py"
BUILD = SKILL / "scripts" / "build_voiceover.py"


def run(script, *args):
    return subprocess.run([sys.executable, str(script), *[str(a) for a in args]],
                          capture_output=True, text=True)


def make_project(tmp_path, beats):
    """beats: list of raw beat text (with citation markers, markdown, etc.)."""
    (tmp_path / "beats").mkdir()
    entries = []
    for i, text in enumerate(beats, start=1):
        fname = f"beats/beat-{i:02d}.md"
        (tmp_path / fname).write_text(text, encoding="utf-8")
        entries.append({"n": i, "words": len(text.split()), "text_file": fname})
    handoff = tmp_path / "handoff.json"
    handoff.write_text(json.dumps({"title": "t", "beats": entries}), encoding="utf-8")
    return handoff


def split(tmp_path, handoff, *extra):
    out = tmp_path / "clauses.json"
    proc = run(SPLIT, handoff, "--project-dir", tmp_path, "-o", out, *extra)
    assert proc.returncode == 0, proc.stderr
    return json.loads(out.read_text())


# --------------------------------------------------------------- clause splitting

def test_short_sentence_stays_one_clause(tmp_path):
    h = make_project(tmp_path, ["She turned sideways."])
    clauses = split(tmp_path, h)["clauses"]
    assert len(clauses) == 1
    assert clauses[0]["mark"] == "b01c01"


def test_long_sentence_splits_on_commas(tmp_path):
    text = ("The wind came across the beam at forty knots, on a hull stacked nine "
            "containers high, and the sand shifted under the bow slowly today.")
    h = make_project(tmp_path, [text])
    clauses = split(tmp_path, h)["clauses"]
    assert len(clauses) > 1


def test_comma_in_number_is_not_a_split_point(tmp_path):
    text = ("The ship displaced 220,000 tonnes of water when it finally moved, which "
            "nobody had predicted at the start of the whole operation.")
    h = make_project(tmp_path, [text])
    clauses = split(tmp_path, h)["clauses"]
    assert not any(c["text"].strip() == "000 tonnes" or c["text"].startswith("000")
                  for c in clauses)
    rejoined = " ".join(c["text"] for c in clauses)
    assert "220,000" in rejoined


def test_citations_stripped_without_stray_space(tmp_path):
    h = make_project(tmp_path, ["She was four hundred metres of steel [C002], and she turned."])
    clauses = split(tmp_path, h)["clauses"]
    text = clauses[0]["text"]
    assert "[C" not in text
    assert "  " not in text
    assert " ," not in text


def test_marks_numbered_per_beat(tmp_path):
    h = make_project(tmp_path, ["First beat sentence here.", "Second beat sentence here."])
    clauses = split(tmp_path, h)["clauses"]
    assert clauses[0]["mark"] == "b01c01"
    assert clauses[1]["mark"] == "b02c01"


def test_empty_beat_rejected(tmp_path):
    h = make_project(tmp_path, [""])
    proc = run(SPLIT, h, "--project-dir", tmp_path)
    assert proc.returncode == 2


def test_ssml_contains_every_mark(tmp_path):
    h = make_project(tmp_path, ["First sentence.", "Second sentence here now."])
    out = tmp_path / "c.json"
    ssml = tmp_path / "s.xml"
    run(SPLIT, h, "--project-dir", tmp_path, "-o", out, "--emit-ssml", ssml)
    clauses = json.loads(out.read_text())["clauses"]
    xml = ssml.read_text()
    assert xml.startswith("<speak>") and xml.strip().endswith("</speak>")
    for c in clauses:
        assert f'name="{c["mark"]}"' in xml


def test_plain_and_offsets_agree_on_every_clause(tmp_path):
    """The invariant the whole ElevenLabs path depends on."""
    text = ("She was four hundred metres of steel, and she turned sideways. The wind "
            "came across the beam at forty knots, on a hull stacked nine containers "
            "high, and the sand shifted under the bow, silently, without warning.")
    h = make_project(tmp_path, [text])
    out, plain, offs = tmp_path / "c.json", tmp_path / "p.txt", tmp_path / "o.json"
    run(SPLIT, h, "--project-dir", tmp_path, "-o", out,
        "--emit-plain", plain, "--emit-offsets", offs)
    plain_text = plain.read_text()
    offsets = json.loads(offs.read_text())["offsets"]
    assert len(offsets) == len(json.loads(out.read_text())["clauses"])
    for o in offsets:
        idx = o["char_offset"]
        assert plain_text[idx] == o["text"][0], (
            f"{o['mark']}: offset {idx} points at {plain_text[idx]!r}, "
            f"clause starts with {o['text'][0]!r}")


# ------------------------------------------------------------- voiceover build

def synth_vertex_response(clauses, gap=3.5):
    t, tps = 0.0, []
    for c in clauses:
        tps.append({"markName": c["mark"], "timeSeconds": round(t, 3)})
        t += gap
    return {"timepoints": tps, "audioConfig": {"durationSeconds": round(t, 3)}}


def synth_elevenlabs_response(plain_text, rate=0.045):
    t, starts, ends = 0.0, [], []
    for _ in plain_text:
        starts.append(round(t, 4))
        t += rate
        ends.append(round(t, 4))
    return {"alignment": {"characters": list(plain_text),
                          "character_start_times_seconds": starts,
                          "character_end_times_seconds": ends}}


def build_project(tmp_path, text):
    h = make_project(tmp_path, [text])
    out, plain, offs = tmp_path / "c.json", tmp_path / "p.txt", tmp_path / "o.json"
    run(SPLIT, h, "--project-dir", tmp_path, "-o", out,
        "--emit-plain", plain, "--emit-offsets", offs)
    return json.loads(out.read_text())["clauses"], plain.read_text(), offs


TEXT = ("She was four hundred metres of steel, and she turned sideways. The wind "
        "came across the beam at forty knots, and the sand shifted under the bow.")


def test_vertex_path_produces_shared_schema(tmp_path):
    clauses, plain, offs = build_project(tmp_path, TEXT)
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps(synth_vertex_response(clauses)), encoding="utf-8")
    out = tmp_path / "vo.json"
    proc = run(BUILD, resp, "--backend", "vertex", "--audio-file", "vo.wav", "-o", out)
    assert proc.returncode == 0, proc.stderr
    vo = json.loads(out.read_text())
    assert len(vo["marks"]) == len(clauses)
    assert vo["backend"] == "vertex"
    assert all("time_s" in m for m in vo["marks"])


def test_elevenlabs_path_produces_shared_schema(tmp_path):
    clauses, plain, offs = build_project(tmp_path, TEXT)
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps(synth_elevenlabs_response(plain)), encoding="utf-8")
    out = tmp_path / "vo.json"
    proc = run(BUILD, resp, "--backend", "elevenlabs", "--offsets", offs,
              "--audio-file", "vo.mp3", "-o", out)
    assert proc.returncode == 0, proc.stderr
    vo = json.loads(out.read_text())
    assert len(vo["marks"]) == len(clauses)
    assert vo["backend"] == "elevenlabs"


def test_both_backends_agree_on_mark_names_for_same_script(tmp_path):
    """The shared schema means shot-forge cannot tell which backend spoke it."""
    clauses, plain, offs = build_project(tmp_path, TEXT)
    vresp = tmp_path / "v.json"
    vresp.write_text(json.dumps(synth_vertex_response(clauses)), encoding="utf-8")
    eresp = tmp_path / "e.json"
    eresp.write_text(json.dumps(synth_elevenlabs_response(plain)), encoding="utf-8")

    vout, eout = tmp_path / "vo_v.json", tmp_path / "vo_e.json"
    run(BUILD, vresp, "--backend", "vertex", "--audio-file", "a.wav", "-o", vout)
    run(BUILD, eresp, "--backend", "elevenlabs", "--offsets", offs,
        "--audio-file", "a.mp3", "-o", eout)

    v_names = [m["name"] for m in json.loads(vout.read_text())["marks"]]
    e_names = [m["name"] for m in json.loads(eout.read_text())["marks"]]
    assert v_names == e_names


def test_elevenlabs_requires_offsets_flag(tmp_path):
    clauses, plain, offs = build_project(tmp_path, TEXT)
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps(synth_elevenlabs_response(plain)), encoding="utf-8")
    proc = run(BUILD, resp, "--backend", "elevenlabs", "--audio-file", "vo.mp3")
    assert proc.returncode == 2


def test_drifted_alignment_text_rejected(tmp_path):
    """The check that catches silent timing corruption before it reaches shot-forge."""
    clauses, plain, offs = build_project(tmp_path, TEXT)
    resp_data = synth_elevenlabs_response(plain)
    target = json.loads(Path(offs).read_text())["offsets"][1]["char_offset"]
    resp_data["alignment"]["characters"][target] = "#"
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps(resp_data), encoding="utf-8")
    proc = run(BUILD, resp, "--backend", "elevenlabs", "--offsets", offs,
              "--audio-file", "vo.mp3")
    assert proc.returncode == 1
    assert "drifted" in proc.stderr


def test_offset_past_end_of_alignment_rejected(tmp_path):
    clauses, plain, offs = build_project(tmp_path, TEXT)
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps(synth_elevenlabs_response(plain)), encoding="utf-8")
    bad_offs = json.loads(Path(offs).read_text())
    bad_offs["offsets"][0]["char_offset"] = 999999
    bad_path = tmp_path / "bad_offs.json"
    bad_path.write_text(json.dumps(bad_offs), encoding="utf-8")
    proc = run(BUILD, resp, "--backend", "elevenlabs", "--offsets", bad_path,
              "--audio-file", "vo.mp3")
    assert proc.returncode == 1
    assert "outside the alignment" in proc.stderr


def test_non_increasing_marks_rejected(tmp_path):
    clauses, plain, offs = build_project(tmp_path, TEXT)
    resp_data = synth_vertex_response(clauses)
    resp_data["timepoints"][1]["timeSeconds"] = resp_data["timepoints"][0]["timeSeconds"]
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps(resp_data), encoding="utf-8")
    proc = run(BUILD, resp, "--backend", "vertex", "--audio-file", "vo.wav")
    assert proc.returncode == 1
    assert "not strictly increasing" in proc.stderr


def test_missing_timepoints_rejected(tmp_path):
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps({"audioConfig": {"durationSeconds": 10}}), encoding="utf-8")
    proc = run(BUILD, resp, "--backend", "vertex", "--audio-file", "vo.wav")
    assert proc.returncode == 2


def test_clause_text_attached_when_requested(tmp_path):
    clauses, plain, offs = build_project(tmp_path, TEXT)
    out_clauses = tmp_path / "c.json"  # already written by build_project's split call
    resp = tmp_path / "r.json"
    resp.write_text(json.dumps(synth_vertex_response(clauses)), encoding="utf-8")
    out = tmp_path / "vo.json"
    run(BUILD, resp, "--backend", "vertex", "--audio-file", "vo.wav",
        "--clauses", out_clauses, "-o", out)
    vo = json.loads(out.read_text())
    assert all("text" in m and m["text"] for m in vo["marks"])
