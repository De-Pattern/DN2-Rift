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
    assert ("ORGAN's pipes, gains and ramp (dnfw.organ.program.tables_bytes; RIFT)", dsp.ORGAN_TABLES_DDR,
            P.tables_bytes()) in dsp.ddr_spans()
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
