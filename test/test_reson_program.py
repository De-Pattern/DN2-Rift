"""RESONATOR's DSP program (run mode) is live.Voice bit for bit: notes, every knob moving, extreme
panels, a voice ringing out to rest and a note after it. The SHARC runner's `reson` part holds the
assembled code to this run mode."""
import random

import numpy as np
import pytest

from dnfw.reson import bench as B
from dnfw.reson import ddr
from dnfw.reson import live as L
from dnfw.reson import program as P


def test_the_committed_tables_are_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()


def test_defaults_three_notes():
    a, b, first = B.compare(lambda k: B.panel_knobs(), {1: 48.0, 200: 55.0, 400: 84.5}, 600)
    assert first is None, first
    assert np.abs(b).max() > 0.05


@pytest.mark.parametrize("seed", range(5))
def test_extreme_panels(seed):
    def kn(k):
        r = random.Random(seed * 1000 + k // 9)
        return [r.choice([0, 127, r.randrange(128)]) for _ in range(8)]
    a, b, first = B.compare(kn, {1: 30.0 + 11 * seed, 40: 100.0, 80: 20.5, 81: 127.0}, 140)
    assert first is None, first


def test_every_knob_moving():
    base = B.panel_knobs()

    def kn(k):
        return [(base[j] + 5 * k * (j + 1)) % 128 for j in range(8)]
    a, b, first = B.compare(kn, {1: 60.0, 30: 62.0, 60: 36.0}, 90)
    assert first is None, first


def test_a_voice_rings_out_to_rest_and_wakes():
    a, b, first = B.compare(lambda k: B.panel_knobs(DAMP=0, BRIT=0), {1: 60.0, 2900: 64.0}, 2950)
    assert first is None, first
    assert (b[2800 * 32:2900 * 32] == 0).all() and np.abs(b[2900 * 32:]).max() > 0.01


def test_the_comparison_sees_a_wrong_program():
    """negative control: live with another knob than the frame's is caught"""
    kn = B.panel_knobs()
    dsp = B.Dsp()
    v = L.Voice(0)
    seen = None
    for k in range(20):
        f = B.Frame()
        words = B.knobs_words(kn)
        f.res(0, words, 48.0, k == 1)
        got = dsp.block(f, [0])[0]
        other = list(B.knobs_seen(words))
        other[2] += 1
        want = v.block(other, k == 1, 48.0)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = k
            break
    assert seen is not None
