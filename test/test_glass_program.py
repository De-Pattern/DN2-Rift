"""RUBBER's DSP program (v0.24, the FLTR type 6 in GLASS's place; run mode) is live.Voice bit for bit: the
defaults, DRIVE, RES from 0 to self-oscillation, the envelope with both bends both ways, key tracking, a huge
input (the soft clip), two slots at once with their own states, a slot on another filter left as it was,
and a negative control."""
import random

import numpy as np
import pytest

from dnfw.glass import bench as B
from dnfw.glass import live as L


def test_defaults_and_it_rings():
    a, b, first = B.compare(lambda k: B.rec_floats(), {1: 60.0, 30: 64.0}, 60)
    assert first is None, first
    assert np.abs(a).max() > 0.05


@pytest.mark.parametrize("seed", range(5))
def test_random_settings(seed):
    r = random.Random(seed)

    def rec(k):
        r2 = random.Random(seed * 1000 + k // 7)
        return B.rec_floats(TYPE=r2.random(), FREQ=r2.random(), RES=r2.choice([0.0, 1.0, r2.random()]),
                            ATK=r2.random(), DEC=r2.random(),
                            ABND=r2.choice([0.0, 0.5, 1.0, r2.random()]), DBND=r2.choice([0.0, 1.0, r2.random()]),
                            DEPTH=r2.random(), KEYT=r2.random())
    _ = r
    a, b, first = B.compare(rec, {1: 48.0, 20: 72.0, 41: 36.0}, 60)
    assert first is None, first
    assert np.isfinite(a).all()


@pytest.mark.parametrize("ab,db", [(0.0, 0.0), (1.0, 1.0), (0.0, 1.0), (0.25, 0.8)])
def test_envelope_bends(ab, db):
    a, b, first = B.compare(lambda k: B.rec_floats(DEPTH=0.9, ATK=0.4, DEC=0.4, ABND=ab, DBND=db), {1: 60.0}, 50)
    assert first is None, first


def test_self_oscillates_at_the_top():
    """RES at its top rings on with no input (a kick to start it), bounded"""
    def kick(k):
        x = np.zeros(32, np.float32)
        if k == 1:
            x[0] = 0.5
        return x
    a, b, first = B.compare(lambda k: B.rec_floats(RES=1.0, FREQ=0.5), {1: 60.0}, 120, src=kick)
    assert first is None, first
    assert np.abs(a[-32 * 20:]).max() > 0.05 and np.abs(a).max() < 2.0


def test_a_huge_input_stays_bounded():
    def loud(k):
        x = np.zeros(32, np.float32)
        if k % 10 == 1:
            x[0] = 50.0
        return x
    a, b, first = B.compare(lambda k: B.rec_floats(RES=1.0, TYPE=0.5), {1: 60.0}, 60, src=loud)
    assert first is None, first
    assert np.isfinite(a).all() and np.abs(a).max() < 4.0


def test_two_slots_their_own_states_and_another_filter_untouched():
    dsp = B.Dsp()
    v2, v9 = L.Voice(), L.Voice()
    for kb in range(40):
        f = B.Frame()
        r2, r9 = B.rec_floats(FREQ=0.5, RES=0.9), B.rec_floats(FREQ=0.8, TYPE=1.0, DEPTH=0.8)
        x2, x9, x5 = B.source(kb, 1), B.source(kb, 2), B.source(kb, 3)
        f.glass(2, r2, 60.0, kb == 1, x2)
        f.glass(9, r9, 67.0, kb == 3, x9)
        f.glass(5, r2, 60.0, kb == 1, x5, ftype=0)          # Multi-Mode: not ours
        got = dsp.block(f, [2, 5, 9])
        w2 = v2.block(r2, kb == 1, B.FB.note_seen(60.0), x2)
        w9 = v9.block(r9, kb == 3, B.FB.note_seen(67.0), x9)
        assert np.array_equal(got[2].view(np.uint32), w2.view(np.uint32)), (kb, 2)
        assert np.array_equal(got[9].view(np.uint32), w9.view(np.uint32)), (kb, 9)
        assert np.array_equal(got[5].view(np.uint32), x5.view(np.uint32)), (kb, 5)


def test_the_comparison_sees_a_wrong_program():
    dsp = B.Dsp()
    v = L.Voice()
    seen = None
    for kb in range(20):
        rec = B.rec_floats()
        x = B.source(kb)
        f = B.Frame()
        f.glass(2, rec, 60.0, kb == 1, x)
        got = dsp.block(f, [2])[2]
        r2 = dict(rec)
        r2[L.R_FREQ] = np.float32(r2[L.R_FREQ] + np.float32(1.0 / 128))
        want = v.block(r2, kb == 1, B.FB.note_seen(60.0), x)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = kb
            break
    assert seen == 0


def test_emits():
    from dnfw.fascia import program as FP_
    from dnfw.glass import program as P
    p = FP_.FProg("emit", prefix="gls")
    p.pool = {}
    p.spill = None
    L_ = P.Layout(FP_.layout(), B.STATE)
    p.scr = (L_.scratch, L_.scratch_end, L_.base5)
    g = P.walk(p, L_)
    g.emit_rts()
    p.emit_subs()
    n = sum(1 for x in p.lines if x.startswith("      ") and not x.strip().startswith("//"))
    print("instructions", n)
    assert 200 < n < 1400




@pytest.mark.parametrize("amp,typ,res", [(0.5, 0.0, 0.2), (2.0, 0.25, 0.9), (6.0, 0.75, 1.0), (30.0, 1.0, 0.6)])
def test_v024_registers_same_bits_as_words(amp, typ, res):
    """v0.24: RUBBER's samples_fast (registers) against sample() (words) and live, every block bit for bit:
    quiet, the soft clip's middle and its top, DRIVE's range"""
    from dnfw.glass import program as P

    def run(fast):
        rng = np.random.default_rng(int(amp * 10))
        P.FAST = fast
        try:
            return B.compare(lambda k: B.rec_floats(TYPE=typ, RES=res, FREQ=0.55, DEPTH=0.8, ATK=0.2, DEC=0.5),
                             {1: 60.0, 25: 64.0}, 30, src=lambda k: (amp * rng.standard_normal(32)).astype(np.float32))
        finally:
            P.FAST = True
    (a1, _b, f1), (a2, _c, f2) = run(True), run(False)
    assert f1 is None and f2 is None, (f1, f2)
    assert np.array_equal(a1.view(np.uint32), a2.view(np.uint32))
    assert np.abs(a1).max() > 1e-3
