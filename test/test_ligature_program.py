"""LIGATURE's DSP program (run mode) is live.SlotVoice bit for bit: every patch, notes, velocities,
note-offs, every setting moving, extreme panels, a patch change mid-note, a release to rest and a note
after it. The SHARC runner's `ligature` part holds the assembled code to this run mode."""
import random

import numpy as np
import pytest

from dnfw.ligature import bench as B
from dnfw.ligature import live as L
from dnfw.ligature import program as P
from dnfw.ligature import ddr


def test_the_committed_tables_are_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()


@pytest.mark.parametrize("pk", range(L.NP))
def test_every_patch_with_its_settings_moving(pk):
    base = B.panel_knobs(PATCH=pk)

    def kn(k):
        x = list(base)
        for j in range(8, 32):
            x[j] = (base[j] + k * (j + 3)) % 128
        return x
    a, b, first = B.compare(kn, {1: 36.0 + pk, 25: 60.5, 50: 72.0}, 70, offs=(15, 45), vels={1: 127, 25: 40, 50: 90})
    assert first is None, first
    assert np.abs(b).max() > 0.01


@pytest.mark.parametrize("seed", range(6))
def test_extreme_panels(seed):
    r0 = random.Random(seed)
    pk = r0.randrange(L.NP)

    def kn(k):
        r = random.Random(seed * 1000 + k // 7)
        x = [r.choice([0, 127, r.randrange(128)]) for _ in range(32)]
        x[0] = B.panel_knobs(PATCH=pk)[0]
        return x
    a, b, first = B.compare(kn, {1: 30.0 + 7 * seed, 30: 90.0}, 60, offs=(20,))
    assert first is None, first


def test_a_patch_change_mid_note():
    a, b, first = B.compare(lambda k: B.panel_knobs(PATCH=(k // 20) % L.NP), {1: 48.0}, 120, offs=(70,))
    assert first is None, first


def test_a_released_voice_rests_and_wakes():
    a, b, first = B.compare(lambda k: B.panel_knobs(PATCH="PLONK"), {1: 48.0, 900: 50.0}, 920, offs=(3,))
    assert first is None, first
    assert (b[850 * 32:900 * 32] == 0).all() and np.abs(b[900 * 32:]).max() > 0.01


def test_the_comparison_sees_a_wrong_program():
    """negative control: live with another knob than the frame's is caught"""
    kn = B.panel_knobs(PATCH="INIT")
    dsp = B.Dsp()
    v = L.SlotVoice(0)
    seen = None
    for k in range(20):
        f = B.Frame()
        words = B.knobs_words(kn)
        f.lig(0, words, 48.0, k == 1, 127, False)
        got = dsp.block(f, [0])[0]
        other = list(B.knobs_seen(words))
        other[8] += 1
        want = v.dsp_block(other, k == 1, 48.0, 127, False)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = k
            break
    assert seen is not None
