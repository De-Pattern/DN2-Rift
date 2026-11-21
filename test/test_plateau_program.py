"""PLATEAU's DSP program (run mode) is live.Voice bit for bit: the defaults, random panels (every
control, both switches), every knob moving, TUNED following the notes, HOLD with DRV, a long PRED, the
bus (its mask, the slot's own track left out), a voice resting and waking, one instance (the newest
voice owns the lines), and a negative control."""
import random

import numpy as np
import pytest

from dnfw.plateau import bench as B
from dnfw.plateau import ddr
from dnfw.plateau import live as L
from dnfw.plateau import machines as PM
from dnfw.plateau import program as P

CLEAR = -(-L.TOTAL // L.CHUNK)          # the fresh instance's silent blocks


def test_the_committed_tables_are_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()


def test_defaults_bit_for_bit_and_it_sounds():
    a, b, first = B.compare(lambda k: B.panel_knobs(), {0: 60.0}, CLEAR + 60)
    assert first is None, first
    assert not a[:CLEAR * 32].any()                  # silent while the lines clear
    assert np.abs(a[CLEAR * 32:]).max() > 1e-3


@pytest.mark.parametrize("seed", range(4))
def test_random_panels(seed):
    def kn(k):
        r = random.Random(seed * 1000 + k // 9)
        return [r.choice([0, 127, r.randrange(128)]) for _ in range(16)]
    a, b, first = B.compare(kn, {0: 50.0 + 7 * seed, 40: 62.0}, CLEAR + 50, seed=seed)
    assert first is None, first


def test_every_knob_moving():
    base = B.panel_knobs()

    def kn(k):
        return [(base[j] + 5 * k * (j + 1)) % 128 for j in range(16)]
    a, b, first = B.compare(kn, {0: 60.0, 30: 64.0}, CLEAR + 45)
    assert first is None, first


def test_tuned_follows_the_notes():
    a, b, first = B.compare(lambda k: B.panel_knobs(TUND=1, DCAY=110), {0: 48.0, 35: 60.0, 45: 67.0}, CLEAR + 50)
    assert first is None, first


def test_hold_and_drive_and_predelay():
    def kn(k):
        return B.panel_knobs(HOLD=1 if k > CLEAR + 20 else 0, DRV=127, PRED=127, DCAY=127, IGN=127)
    a, b, first = B.compare(kn, {0: 60.0}, CLEAR + 40)
    assert first is None, first
    assert np.isfinite(a).all() and np.abs(a).max() < 4.0


def test_the_bus_leaves_out_the_slots_own_track():
    """the slot plays track 5, which is in the mask: never summed (else the output differs)"""
    mask = 0xFFFF
    a, b, first = B.compare(lambda k: B.panel_knobs(), {0: 60.0}, CLEAR + 20, mask=mask, track=5)
    assert first is None, first
    a2, _b2, _f = B.compare(lambda k: B.panel_knobs(), {0: 60.0}, CLEAR + 20, mask=mask & ~(1 << 5), track=5)
    assert np.array_equal(a.view(np.uint32), a2.view(np.uint32))


def test_an_empty_mask_is_silent():
    a, b, first = B.compare(lambda k: B.panel_knobs(), {0: 60.0}, CLEAR + 20, mask=0)
    assert first is None, first
    assert not a.any()


def test_a_voice_rests_and_wakes():
    """the bus goes quiet (mask 0 after block 30): a second later the voice rests; a trig wakes it"""
    dsp = B.Dsp()
    v = L.Voice(3)
    outs = []
    n = CLEAR + 30 + L.QUIET_BLOCKS + 1500
    for kb in range(n):
        mask = 0b100101 if kb < CLEAR + 30 else 0
        words = B.knobs_words(B.panel_knobs(DCAY=0))
        trig = kb in (0, n - 20)
        bl, br = B.bus_blocks(kb)
        if kb >= n - 20:
            mask = 0b100101
        f = B.Frame()
        f.plt(3, words, 60.0, trig, mask, 3)
        f.tracks(bl, br)
        got = dsp.block(f, [3])[3]
        want = v.block(B.live_knobs(words), trig, B.FB.note_seen(60.0), L.bus_sum(bl, br, mask, 3))
        assert np.array_equal(got.view(np.uint32), want.view(np.uint32)), kb
        outs.append((v.on, got))
    assert any(on == 0 for on, _o in outs[CLEAR + 30:n - 20])      # rested
    assert not outs[n - 21][1].any()
    assert outs[-1][0] == 1 and np.abs(outs[-1][1]).max() > 0


def test_one_instance_the_newest_owns_it():
    """two slots on PLATEAU: the second's trig takes the lines; the first goes off and silent"""
    dsp = B.Dsp()
    shared = L.Shared()
    v0, v1 = L.Voice(1, shared), L.Voice(6, shared)
    for kb in range(CLEAR + 40):
        words = B.knobs_words(B.panel_knobs())
        bl, br = B.bus_blocks(kb)
        f = B.Frame()
        f.plt(1, words, 60.0, kb == 0, 0b101, 1)
        f.plt(6, words, 60.0, kb == CLEAR + 10, 0b101, 6)
        f.tracks(bl, br)
        got = dsp.block(f, [1, 6])
        bus = L.bus_sum(bl, br, 0b101, 1)
        w0 = v0.block(B.live_knobs(words), kb == 0, B.FB.note_seen(60.0), bus)
        w1 = v1.block(B.live_knobs(words), kb == CLEAR + 10, B.FB.note_seen(60.0), L.bus_sum(bl, br, 0b101, 6))
        assert np.array_equal(got[1].view(np.uint32), w0.view(np.uint32)), (kb, 1)
        assert np.array_equal(got[6].view(np.uint32), w1.view(np.uint32)), (kb, 6)
    assert v0.on == 0 and not got[1].any() and np.abs(got[6]).max() > 0


def test_the_comparison_sees_a_wrong_program():
    """negative control: live with another LEV than the frame's is caught"""
    dsp = B.Dsp()
    v = L.Voice(3)
    seen = None
    for kb in range(CLEAR + 10):
        words = B.knobs_words(B.panel_knobs())
        bl, br = B.bus_blocks(kb)
        f = B.Frame()
        f.plt(3, words, 60.0, kb == 0, 0b100101, 3)
        f.tracks(bl, br)
        got = dsp.block(f, [3])[3]
        lk = B.live_knobs(words)
        lk["LEV"] += 1
        want = v.block(lk, kb == 0, B.FB.note_seen(60.0), L.bus_sum(bl, br, 0b100101, 3))
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = kb
            break
    assert seen is not None and seen >= CLEAR


def test_mask_records_round_trip():
    for m in (0, 1, 0x8000, 0xFFFF, 0b1010110011100101):
        assert PM.mask_of(PM.mask_values(m)) == m
        assert all(0 <= v <= 63 for v in PM.mask_values(m))


def test_emits():
    from dnfw.fascia import program as FP_
    p = FP_.FProg("emit", prefix="plt")
    p.pool = {}
    p.spill = None
    L_ = P.Layout(FP_.layout(), B.TABLES, B.LINES)
    p.scr = (L_.scratch, L_.scratch_end, L_.base5)
    g = P.voice(p, L_)
    g.emit_rts()
    p.emit_subs()
    n = sum(1 for x in p.lines if x.startswith("      ") and not x.strip().startswith("//"))
    print("instructions", n)
    assert 500 < n < 2600


def test_a_bus_that_is_not_a_number_never_reaches_the_lines():
    """a NaN, an infinity or a runaway on the bus is taken as 0: the output stays finite, bit for bit"""
    dsp = B.Dsp()
    v = L.Voice(3)
    for kb in range(CLEAR + 20):
        words = B.knobs_words(B.panel_knobs())
        bl, br = B.bus_blocks(kb)
        if kb in (CLEAR + 3, CLEAR + 9):
            bl[0][5] = np.float32("nan")
            br[2][7] = np.float32("inf")
            bl[5][1] = np.float32(1.0e9)
        f = B.Frame()
        f.plt(3, words, 60.0, kb == 0, 0b100101, 3)
        f.tracks(bl, br)
        got = dsp.block(f, [3])[3]
        want = v.block(B.live_knobs(words), kb == 0, B.FB.note_seen(60.0), L.bus_sum(bl, br, 0b100101, 3))
        assert np.array_equal(got.view(np.uint32), want.view(np.uint32)), kb
        assert np.isfinite(got).all(), kb
    assert np.abs(got).max() > 0
