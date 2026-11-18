"""DIGIDRUM's DSP program (run mode) is live.Voice bit for bit: every type, page 2 on and off, knobs
moving (TYPE among them, so a hit's type changes at the next trig), velocities, a voice ringing out to
rest and waking, and a negative control."""
import random

import numpy as np
import pytest

from dnfw.digidrum import bench as B
from dnfw.digidrum import ddr
from dnfw.digidrum import live as L
from dnfw.digidrum import program as P


def test_the_committed_tables_are_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()


@pytest.mark.parametrize("ty", range(6))
def test_each_type_defaults(ty):
    tk = int(ty * 128 / 6) + 5
    a, b, first = B.compare(lambda k: B.panel_knobs(TYPE=tk), {1: 60.0, 25: 48.0}, 50)
    assert first is None, first
    assert np.abs(b).max() > 0.05


@pytest.mark.parametrize("seed", range(4))
def test_random_panels_and_page_two(seed):
    def kn(k):
        r = random.Random(seed * 1000 + k // 7)
        return [r.choice([0, 127, r.randrange(128)]) for _ in range(16)]
    a, b, first = B.compare(kn, {1: 40.0 + 9 * seed, 14: 72.0, 30: 60.5}, 45, vel=40 + 20 * seed)
    assert first is None, first


def test_every_knob_moving_and_type_changing():
    base = B.panel_knobs()

    def kn(k):
        return [(base[j] + 7 * k * (j + 1)) % 128 for j in range(16)]
    a, b, first = B.compare(kn, {1: 60.0, 10: 62.0, 20: 50.0, 30: 70.0}, 40)
    assert first is None, first


def test_a_voice_rests_and_wakes():
    a, b, first = B.compare(lambda k: B.panel_knobs(TYPE=0, DEC=0), {1: 60.0, 400: 60.0}, 420)
    assert first is None, first
    assert (b[300 * 32:400 * 32] == 0).all() and np.abs(b[400 * 32:]).max() > 0.01


def test_the_comparison_sees_a_wrong_program():
    """negative control: live with another knob than the frame's is caught"""
    kn = B.panel_knobs(TYPE=0)
    dsp = B.Dsp()
    v = L.Voice(0)
    seen = None
    for k in range(20):
        f = B.Frame()
        words = B.knobs_words(kn)
        f.dd(0, words, 60.0, k == 1)
        got = dsp.block(f, [0])[0]
        lk = B.live_knobs(B.knobs_seen(words))
        lk["SWEP"] += 1
        want = v.block(lk, k == 1, 60.0)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = k
            break
    assert seen is not None


def test_emits():
    from dnfw.fascia import program as FP_
    from dnfw.perc.dsl import Prog
    p = FP_.FProg("emit", prefix="ddt")
    p.pool = {}
    p.spill = None
    L_ = P.Layout(FP_.layout(), B.TABLES)
    p.scr = (L_.scratch, L_.scratch_end, L_.base5)
    g = P.voice(p, L_)
    g.emit_rts()
    p.emit_subs()
    n = sum(1 for x in p.lines if x.startswith("      ") and not x.strip().startswith("//"))
    print("instructions", n)
    assert n > 500
