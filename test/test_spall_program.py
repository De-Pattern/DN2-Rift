"""SPALL's DSP program (run mode) is live.Voice bit for bit: every particle type, every oscillator algorithm,
clumps and memory, every knob moving, random panels, retrigs, and a negative control."""
import random

import numpy as np
import pytest

from dnfw.spall import bench as B
from dnfw.spall import ddr
from dnfw.spall import live as L
from dnfw.spall import program as P


def test_the_committed_tables_are_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()


@pytest.mark.parametrize("ty", range(4))
@pytest.mark.parametrize("alg", range(3))
def test_each_type_and_algorithm(ty, alg):
    a, b, first = B.compare(lambda k: B.panel_knobs(TYPE=32 * ty + 5, ALG=43 * alg + 5, DENS=100, SIZE=70,
                                                    CLMP=60, GAP=30),
                            {1: 52.0}, 24)
    assert first is None, first
    assert np.abs(b).max() > 0.01


def test_memory_repeats_and_single_events():
    a, b, first = B.compare(lambda k: B.panel_knobs(MEM=40, DENS=110, TYPE=70), {1: 60.0, 20: 48.0}, 30)
    assert first is None, first
    a, b, first = B.compare(lambda k: B.panel_knobs(DENS=0, RING=110, MIX=127), {1: 60.0, 9: 67.0}, 16)
    assert first is None, first


@pytest.mark.parametrize("seed", range(4))
def test_random_panels(seed):
    def kn(k):
        r = random.Random(seed * 1000 + k // 5)
        return [r.choice([0, 127, r.randrange(128)]) for _ in range(16)]
    a, b, first = B.compare(kn, {1: 40.0 + 9 * seed, 14: 72.0, 22: 60.5}, 28)
    assert first is None, first


def test_every_knob_moving():
    base = B.panel_knobs()

    def kn(k):
        return [(base[j] + 7 * k * (j + 1)) % 128 for j in range(16)]
    a, b, first = B.compare(kn, {1: 60.0, 10: 62.0, 20: 50.0}, 28)
    assert first is None, first


def test_silent_before_a_note():
    a, b, first = B.compare(lambda k: B.panel_knobs(), {12: 60.0}, 16)
    assert first is None and not np.abs(a[:12 * 32]).any() and np.abs(a[12 * 32:]).max() > 0.01


def test_the_comparison_sees_a_wrong_program():
    """negative control: live with another knob than the frame's is caught"""
    kn = B.panel_knobs(TYPE=70)
    dsp = B.Dsp()
    v = L.Voice()
    seen = None
    for k in range(20):
        f = B.Frame()
        words = B.knobs_words(kn)
        f.dd(0, words, 60.0, k == 1)
        got = dsp.block(f, [0])[0]
        lk = B.live_knobs(B.knobs_seen(words))
        lk["TUNE"] += 1
        want = v.block(lk, B.FB.note_seen(60.0), k == 1)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = k
            break
    assert seen is not None


def test_levels_are_sane():
    for kn in ({}, dict(TYPE=40), dict(TYPE=80, ALG=100, DENS=70), dict(TYPE=120, CLMP=80, DENS=80)):
        y = L.render(0.5, **kn)
        assert np.isfinite(y).all() and np.abs(y).max() <= 0.9 and np.abs(y).max() > 0.01


def test_emits():
    from dnfw.fascia import program as FP_
    p = FP_.FProg("emit", prefix="spt")
    p.pool = {}
    p.spill = None
    L_ = P.Layout(FP_.layout(), B.TABLES)
    p.scr = (L_.scratch, L_.scratch_end, L_.base5)
    g = P.voice(p, L_)
    g.emit_rts()
