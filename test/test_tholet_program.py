"""THOLET's DSP program (run mode) is live.Voice bit for bit (the concept is Error Kit's): the strikes,
the strings, FELT, EP, the damper, knob changes mid-note, a retrigger, the cloud (after the ring's
clearing), rest and wake; and a negative control. The SHARC runner's `tholet` part holds the
assembled code to this run mode."""
import random

import numpy as np
import pytest

from dnfw.tholet import bench as B
from dnfw.tholet import ddr
from dnfw.tholet import live as L
from dnfw.tholet import machines as TM
from dnfw.tholet import program as P


def test_the_committed_tables_are_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()


def test_the_voice_fits_and_the_tables_hold_the_strikes():
    assert 4 * P.VOICE_WORDS <= P.STRIDE
    assert P.TAB["HITS"][1] == L.NH * ((L.HIT_N + 3) // 4)
    assert len(L.MULAW) == 256 and len(TM.HITS) == L.NH


@pytest.mark.parametrize("hamr", range(6))
def test_each_strike_with_a_note_off(hamr):
    kn = lambda k: B.panel_knobs(HAMR=TM.rep_word and [k2 for k2 in range(128) if TM.option("HAMR", k2) == hamr][0])
    a, b, first = B.compare(kn, {1: 48.0 + 5 * hamr}, 40, vel=90, offs=(25,))
    assert first is None, first
    assert np.abs(b).max() > 0.01


@pytest.mark.parametrize("kw", [dict(FELT=110), dict(EP=120, STRK=127), dict(TONE=0, DEC=10), dict(TONE=127, DEC=127),
                                dict(TUNE=0), dict(TUNE=127, BRTH=127, VSNS=0), dict(LEV=0)])
def test_the_controls(kw):
    a, b, first = B.compare(lambda k: B.panel_knobs(**kw), {1: 60.0, 20: 72.0}, 36, vel=127, offs=(30,))
    assert first is None, first


def test_knobs_moving_mid_note_retune_in_place():
    def kn(k):
        return B.panel_knobs(TUNE=64 + (k % 9), EP=(k * 7) % 128, FELT=(k * 3) % 128, STRK=k % 128, DEC=40 + k)
    a, b, first = B.compare(kn, {1: 55.0}, 40, offs=(28,))
    assert first is None, first


def test_the_cloud_after_the_ring_clears():
    kn = lambda k: B.panel_knobs(GRAN=120, GDEN=127, GSIZ=20, GFM=90, GSPR=100, DEC=120)
    a, b, first = B.compare(kn, {1: 60.0, 34: 67.0, 60: 52.0}, 110, vel=110, offs=(90,))
    assert first is None, first
    assert np.abs(b[40 * 32:]).max() > 0.01


@pytest.mark.parametrize("seed", range(4))
def test_random_panels(seed):
    r = random.Random(seed)

    def kn(k):
        rr = random.Random(seed * 1000 + k // 9)
        return [rr.choice([0, 127, rr.randrange(128)]) for _ in range(16)]
    ev = {1 + 13 * j: float(r.randrange(24, 100)) for j in range(5)}
    a, b, first = B.compare(kn, ev, 70, vel=r.randrange(1, 128), offs=(10, 40))
    assert first is None, first
    assert np.isfinite(a).all()


def test_a_voice_rests_and_wakes():
    a, b, first = B.compare(lambda k: B.panel_knobs(DEC=0, REL=0), {1: 72.0, 300: 60.0}, 320, offs=(3,))
    assert first is None, first
    assert (b[260 * 32:300 * 32] == 0).all() and np.abs(b[300 * 32:]).max() > 0.01


def test_the_comparison_sees_a_wrong_program():
    """negative control: live hearing another TONE than the frame's is caught"""
    dsp = B.Dsp()
    v = L.Voice(0)
    seen = None
    for k in range(10):
        words = B.knobs_words(B.panel_knobs())
        f = B.Frame()
        f.dd(0, words, 60.0, k == 1, 100)
        got = dsp.block(f, [0])[0]
        kk = B.live_knobs(B.knobs_seen(words))
        kk["TONE"] += 1
        want = v.block(kk, k == 1, 60.0, 100, False)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = k
            break
    assert seen is not None
