"""CONTOUR's DSP program (run mode) is live.Voice bit for bit: every surface, MORPH on, every knob moving,
random panels, retrigs, and a negative control."""
import random

import numpy as np
import pytest

from dnfw.contour import bench as B
from dnfw.contour import ddr
from dnfw.contour import live as L
from dnfw.contour import program as P


def test_the_committed_tables_are_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()


@pytest.mark.parametrize("s", range(8))
def test_each_surface(s):
    a, b, first = B.compare(lambda k: B.panel_knobs(SURF=16 * s + 3), {1: 48.0}, 30)
    assert first is None, first
    assert np.abs(b).max() > 0.02


@pytest.mark.parametrize("s", range(8))
def test_each_surface_morphed_folded(s):
    a, b, first = B.compare(lambda k: B.panel_knobs(SURF=16 * s + 3, MORPH=70, FOLD=40, GRIT=20, FM=50, FDBK=40,
                                                    WARP=60, DRFT=90, ROT=33),
                            {1: 52.0, 15: 40.0}, 26)
    assert first is None, first


@pytest.mark.parametrize("seed", range(4))
def test_random_panels(seed):
    def kn(k):
        r = random.Random(seed * 1000 + k // 5)
        return [r.choice([0, 127, r.randrange(128)]) for _ in range(16)]
    a, b, first = B.compare(kn, {1: 40.0 + 9 * seed, 14: 72.0, 22: 60.5}, 30)
    assert first is None, first


def test_every_knob_moving():
    base = B.panel_knobs()

    def kn(k):
        return [(base[j] + 7 * k * (j + 1)) % 128 for j in range(16)]
    a, b, first = B.compare(kn, {1: 60.0, 10: 62.0, 20: 50.0}, 30)
    assert first is None, first


def test_silent_before_a_note():
    a, b, first = B.compare(lambda k: B.panel_knobs(), {12: 60.0}, 16)
    assert first is None and not np.abs(a[:12 * 32]).any() and np.abs(a[12 * 32:]).max() > 0.01


def test_the_comparison_sees_a_wrong_program():
    """negative control: live with another knob than the frame's is caught"""
    kn = B.panel_knobs()
    dsp = B.Dsp()
    v = L.Voice()
    seen = None
    for k in range(20):
        f = B.Frame()
        words = B.knobs_words(kn)
        f.dd(0, words, 60.0, k == 1)
        got = dsp.block(f, [0])[0]
        lk = B.live_knobs(B.knobs_seen(words))
        lk["SIZX"] += 1
        want = v.block(lk, B.FB.note_seen(60.0), k == 1)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = k
            break
    assert seen is not None


def test_emits():
    from dnfw.fascia import program as FP_
    p = FP_.FProg("emit", prefix="ctt")
    p.pool = {}
    p.spill = None
    L_ = P.Layout(FP_.layout(), B.TABLES)
    p.scr = (L_.scratch, L_.scratch_end, L_.base5)
    g = P.voice(p, L_)
    g.emit_rts()


def _held(knobs, note, blocks, dsp=None):
    """a held note: the frame carries NOTE every block (B.compare's other blocks read 60)"""
    dsp = dsp or B.Dsp()
    v = L.Voice()
    a, b = [], []
    words = B.knobs_words(knobs)
    for k in range(blocks):
        f = B.Frame()
        f.dd(0, words, note, k == 1)
        a.append(dsp.block(f, [0])[0])
        b.append(v.block(B.live_knobs(B.knobs_seen(words)), B.FB.note_seen(note), k == 1))
    return np.concatenate(a), np.concatenate(b)


@pytest.mark.parametrize("note", [59.0, 60.0, 66.0, 71.5, 76.0, 90.0])
def test_v020_high_notes_with_feedback(note):
    """v0.20 (owner: FDBK and FM out of key from about C4): above B3 a voice with feedback keytracks it
    and takes 2 or 4 steps a sample; the DSP program is live's bit for bit there too"""
    kn = B.panel_knobs(SURF=88, FDBK=40, FM=89, SIZX=53, SIZY=47, ROT=126, DRFT=18, MORPH=78, WARP=119,
                       FOLD=58, RATIO=95, LEV=90)
    a, b = _held(kn, note, 24)
    assert np.array_equal(a.view(np.uint32), b.view(np.uint32))
    assert np.abs(b).max() > 0.01


def test_v020_nothing_changes_at_or_below_b3_or_without_feedback(monkeypatch):
    """the owner: keep FDBK's effect exactly: at or below B3 (or FDBK 0 anywhere) every sample is v0.19's
    (the high-note path off: IXREF out of reach)"""
    cases = [(B.panel_knobs(SURF=88, FDBK=40, FM=89, RATIO=95), n) for n in (36.0, 48.0, 55.0, 59.0)]
    cases += [(B.panel_knobs(SURF=40, FM=60), n) for n in (72.0, 96.0)]
    for kn, note in cases:
        words = B.knobs_words(kn)
        lk = B.live_knobs(B.knobs_seen(words))
        v1 = L.Voice()
        new = np.concatenate([v1.block(lk, note, k == 0) for k in range(20)])
        monkeypatch.setattr(L, "IXREF", L.F(1e9))
        v2 = L.Voice()
        old = np.concatenate([v2.block(lk, note, k == 0) for k in range(20)])
        monkeypatch.undo()
        assert np.array_equal(new.view(np.uint32), old.view(np.uint32)), note
