"""ORGAN's DSP program (dnfw.organ.program, machine type 19) against live.Voice, bit for bit: Ravel's
presets and the extremes, random panels with p-locks moving mid-note and retriggers (steals), every
stop, garbage in the state. Plus the tables and the layout."""
from __future__ import annotations

import importlib.util
import random
from pathlib import Path

import numpy as np
import pytest

from dnfw.fascia import program as FP_
from dnfw.organ import bench as B
from dnfw.organ import live as LV
from dnfw.organ import program as P
from dnfw.waverider import dsp

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("organ_ref", ROOT / "scripts" / "organ_ref.py")
OR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OR)


def panel_of_eff(eff) -> dict:
    return {c: int(v) for c, v in zip(LV.CONTROLS, eff)}


def test_the_tables_are_current_and_shipped():
    assert P.tables_bytes() == P.tables_values()
    # RIFT v0.16: over the sample link (dsp.link_tables), not in the DSP image
    off = dsp.ORGAN_TABLES_DDR - dsp.LINK_TABLES_DDR
    assert dsp.link_tables()[off:off + len(P.tables_bytes())] == P.tables_bytes()
    assert dsp.FSC_TABLES_DDR + 4 * FP_.TABLE_WORDS <= dsp.ORGAN_TABLES_DDR


def test_the_layout_fits():
    L = P.layout()
    assert L.C['k146'] >= L.fl.arrays and L.words_end <= L.fl.scratch_end and L.base5 == L.fl.base5
    assert all(v < L.fl.arrays for k, v in L.fl.C.items() if k.startswith("k"))     # FASCIA's pool untouched
    assert 4 * P.VOICE_WORDS <= P.STRIDE


@pytest.mark.parametrize("name", list(OR.CASES))
def test_ravels_cases_bit_exact(name):
    eff, note = OR.CASES[name]
    panel = panel_of_eff(eff)
    got, want, first = B.compare(lambda k: panel, {0: float(note)}, 60)
    assert first is None, (name, first)
    assert np.max(np.abs(want)) > 0.001 or name == "low"


@pytest.mark.parametrize("stop", range(5))
def test_every_stop(stop):
    got, want, first = B.compare(lambda k: {"STOP": stop, "R16": 90, "R1": 100, "CELESTE": 70}, {0: 48.0, 30: 84.0}, 50)
    assert first is None and np.max(np.abs(want)) > 0.001


@pytest.mark.parametrize("seed", [3, 17, 29])
def test_random_panels_plocks_and_steals_bit_exact(seed):
    rng = random.Random(seed)
    blocks = 120
    base = {c: rng.randrange(128) for c in LV.CONTROLS}
    base["STOP"] = rng.randrange(5)
    moves, k = {}, 0
    while k < blocks:
        k += rng.randrange(6, 30)
        moves[k] = {c: rng.randrange(128) for c in rng.sample(LV.CONTROLS[1:], rng.randrange(1, 4))}
        if rng.random() < 0.3:
            moves[k]["STOP"] = rng.randrange(5)

    def panel(b):
        q = dict(base)
        for at in sorted(moves):
            if at <= b:
                q.update(moves[at])
        return q
    events = {0: float(rng.randrange(30, 90))}
    for _ in range(4):
        events[rng.randrange(5, blocks)] = rng.randrange(24, 100) + rng.random()
    got, want, first = B.compare(panel, events, blocks)
    assert first is None, first


def test_garbage_state_starts_clean():
    """power-on memory in the slot's state: the voice is off until a trig, then exactly live's"""
    rng = random.Random(5)
    trash = {}

    def fill(a):
        return trash.setdefault(a, rng.getrandbits(32))
    d = B.Dsp(fill=fill)
    got, want, first = B.compare(lambda k: {}, {3: 64.0}, 25, dsp=d)
    assert first is None, first


def test_a_long_note_past_the_chiff_floor():
    """the chiff decays past CHIFF_FLOOR (about 2.3 s at 0.9992 a sample): no denormal on the SHARC"""
    v = LV.Voice(LV.tables(), 0)
    v.block(B.knobs_seen(B.knobs_words({})), True, 60.0)
    for _ in range(3600):
        v.block(B.knobs_seen(B.knobs_words({})), False, 60.0)
    assert v.org.chiff == 0.0


# -- v0.5: pages 3 and 4, the velocity, CELESTE's fade, the leaves' floor ------------------------

def test_a_long_tremolo_bit_exact():
    """v0.5: sin_turns past 0.75 (o_sint's floor took 0 there in v0.4: 124 blocks in, the DSP left
    live by up to 1e-4)"""
    got, want, first = B.compare(lambda k: {"TREM": 127, "TRATE": 127}, {0: 60.0}, 400)
    assert first is None, first


@pytest.mark.parametrize("seed", [41, 43, 47])
def test_pages_3_and_4_random_bit_exact(seed):
    rng = random.Random(seed)
    blocks = 140
    base = {c: rng.randrange(128) for c in LV.CONTROLS}
    base["STOP"] = rng.randrange(5)
    moves, k = {}, 0
    while k < blocks:
        k += rng.randrange(6, 30)
        moves[k] = {c: rng.randrange(128) for c in rng.sample(LV.CONTROLS[1:], rng.randrange(1, 5))}

    def panel(b):
        q = dict(base)
        for at in sorted(moves):
            if at <= b:
                q.update(moves[at])
        return q
    events = {0: float(rng.randrange(30, 90))}
    vels = {0: rng.randrange(1, 128)}
    for _ in range(4):
        at = rng.randrange(5, blocks)
        events[at] = rng.randrange(24, 100) + rng.random()
        vels[at] = rng.randrange(1, 128)
    got, want, first = B.compare(panel, events, blocks, vels=vels)
    assert first is None, first


@pytest.mark.parametrize("over", [{"PERC": 110, "PDEC": 50}, {"MIXT": 110, "MTUN": 127}, {"MIXT": 90, "MTUN": 40}, {"KCLK": 120},
                                  {"MIXT": 127, "STOP": 4}, {"MIXT": 120, "MCHR": 127}, {"MIXT": 120, "MCHR": 64, "STOP": 4}, {"ROTR": 127, "RSPD": 127},
                                  {"BRTH": 127, "TURB": 127}, {"BREK": 127, "BDEP": 127, "PRES": 127},
                                  {"BLOM": 127, "EDGE": 127}, {"BLOM": 100}, {"PVEL": 127, "BREK": 90}])
def test_each_new_control_bit_exact_and_sounding(over):
    got, want, first = B.compare(lambda k: over, {0: 55.0, 30: 70.0}, 60, vels={0: 40, 30: 120})
    assert first is None, first
    assert np.max(np.abs(want)) > 0.001


def test_a_v04_sound_is_v04s_organ():
    """stock's record defaults on pages 3 and 4 (live.LEGACY): the DSP plays the organ as with both
    pages at 0, bit for bit"""
    leg = dict(zip(LV.CONTROLS[16:], LV.LEGACY))
    a, _w, first = B.compare(lambda k: leg, {0: 60.0}, 40)
    assert first is None
    b, _w2, first2 = B.compare(lambda k: {}, {0: 60.0}, 40)
    assert first2 is None and np.array_equal(a.view(np.uint32), b.view(np.uint32))


def test_celeste_fades_in_and_out():
    """the CELESTE rank fades over 8 blocks, no step (a tester: a click at CELST 0 <-> 2)"""
    def panel(k):
        return {"CELESTE": 0 if k < 10 or k >= 30 else 40}
    got, want, first = B.compare(panel, {0: 60.0}, 50)
    assert first is None, first


def test_v08_blom_is_the_breaths_attack():
    """v0.8 (Error Kit: BLOM "should act as Attack for the blowing wind, not for the instrument"):
    BLOM alone leaves the tone as it is (it speaks at once); with EDGE up, the breath on top grows
    over BLOM: early the sound is nearer the plain organ than late"""
    plain, _w0, f0 = B.compare(lambda k: {}, {0: 36.0}, 120)
    alone, _w1, f1 = B.compare(lambda k: {"BLOM": 110}, {0: 36.0}, 120)
    assert f0 is None and f1 is None
    assert np.array_equal(plain.view(np.uint32), alone.view(np.uint32))
    breath, _w2, f2 = B.compare(lambda k: {"BLOM": 110, "EDGE": 127}, {0: 36.0}, 120)
    assert f2 is None
    d = breath - plain
    early, late = np.sqrt(np.mean(d[:32 * 20] ** 2)), np.sqrt(np.mean(d[-32 * 20:] ** 2))
    assert early < 0.5 * late


def test_v06_mtun_lowers_the_mixture():
    """MTUN 127 puts the mixture's pipes 36 semitones down: the spectrum's weight falls"""
    hi, _w, f1 = B.compare(lambda k: {"MIXT": 127}, {0: 60.0}, 60)
    lo, _w2, f2 = B.compare(lambda k: {"MIXT": 127, "MTUN": 127}, {0: 60.0}, 60)
    assert f1 is None and f2 is None

    def centroid(x):
        X = np.abs(np.fft.rfft(x))
        fr = np.fft.rfftfreq(len(x), 1 / 48000)
        return float(np.sum(fr * X) / np.sum(X))
    assert centroid(lo) < 0.8 * centroid(hi)
