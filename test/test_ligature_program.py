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


# -- v0.12: the wirings you make ------------------------------------------------------------------
SEED = L.seed_table()


@pytest.mark.parametrize("pk", range(0, L.NP, 3))
def test_the_seeded_table_plays_the_factory_patches_bit_for_bit(pk):
    kn = lambda k: B.panel_knobs(PATCH=pk)
    ev = {1: 40.0 + pk, 30: 64.0}
    a, b, first = B.compare(kn, ev, 50, offs=(20,), table_of=lambda k: SEED)
    assert first is None, first
    a0, _b0, f0 = B.compare(kn, ev, 50, offs=(20,))
    assert f0 is None and np.array_equal(a.view(np.uint32), a0.view(np.uint32))


def _random_wiring(r):
    rows = []
    n = r.randrange(1, L.NB + 1)
    for i in range(n):
        rows.append((r.choice(L.TYPES), r.randrange(L.NSRC), r.randrange(-100, 101), r.randrange(L.NSRC),
                     r.randrange(-100, 101), r.randrange(128), r.randrange(128)))
    return L.encode(rows, r.randrange(1, n + 1), r.randrange(1 << L.NB))


@pytest.mark.parametrize("seed", range(5))
def test_wirings_you_make_are_bit_exact(seed):
    r = random.Random(seed)
    tb = list(SEED)
    for k in range(L.WSLOTS):
        tb[L.WHDR + L.WWORDS * k: L.WHDR + L.WWORDS * (k + 1)] = _random_wiring(r)
    slot = r.randrange(128)
    a, b, first = B.compare(lambda k: [slot] + B.panel_knobs()[1:], {1: 50.0, 25: 62.0}, 45, offs=(15,),
                            table_of=lambda k: tb)
    assert first is None, first


@pytest.mark.parametrize("seed", range(4))
def test_garbage_in_the_table_is_safe_and_bit_exact(seed):
    """any word in the WIRE area reads as a safe wiring (live.decode), the DSP as live"""
    r = random.Random(100 + seed)
    tb = [L.WMAGIC, L.WVERSION] + [r.getrandbits(32) for _ in range(L.WTABLE_WORDS - 2)]
    slot = r.randrange(128)
    a, b, first = B.compare(lambda k: [slot] + B.panel_knobs()[1:], {1: 45.0}, 40, table_of=lambda k: tb)
    assert first is None, first
    assert np.isfinite(a).all()


def test_an_edit_mid_note_and_the_table_arriving():
    """no table, then the seeded one (same sound), then slot 0 edited while the note plays"""
    r = random.Random(7)
    edited = list(SEED)
    edited[L.WHDR: L.WHDR + L.WWORDS] = _random_wiring(r)

    def tb(k):
        return None if k < 10 else SEED if k < 25 else edited
    a, b, first = B.compare(lambda k: B.panel_knobs(PATCH=0)[:1] and [0] + B.panel_knobs()[1:], {1: 48.0}, 50,
                            table_of=tb)
    assert first is None, first


def test_the_comparison_sees_a_wrong_table():
    """negative control: live reading another wiring than the DSP's is caught"""
    r = random.Random(3)
    other = list(SEED)
    other[L.WHDR: L.WHDR + L.WWORDS] = _random_wiring(r)
    dsp = B.Dsp()
    dsp.set_table(SEED)
    v = L.SlotVoice(0)
    v.table = other
    kn = [0] + B.panel_knobs()[1:]
    f = B.Frame()
    words = B.knobs_words(kn)
    f.lig(0, words, 48.0, True)
    got = dsp.block(f, [0])[0]
    want = v.dsp_block(B.knobs_seen(words), True, 48.0, 127, False)
    f2 = B.Frame()
    f2.lig(0, words, 48.0, False)
    got = np.concatenate([got] + [dsp.block(f2, [0])[0] for _ in range(6)])
    want = np.concatenate([want] + [v.dsp_block(B.knobs_seen(words), False, 48.0, 127, False) for _ in range(6)])
    assert not np.array_equal(got.view(np.uint32), want.view(np.uint32))
