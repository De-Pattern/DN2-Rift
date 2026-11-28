"""CONTACT (RIFT, the FX machine's phase 0, THRU): the DSP program's run mode bit for bit against live.block,
every source, GAIN off / unity / top, its own track silent, one voice a track."""
import numpy as np
import pytest

from dnfw.contact import bench as B, live as LV, machines as CM, program as P, ddr


def _src(seed=7):
    return B.sources(np.random.default_rng(seed))


def _want(knobs, src, own):
    k = B.live_knobs(B.knobs_seen(B.knobs_words(knobs)))
    o = LV.option(k["SRC"], LV.NSRC)
    lr = src["in"] if o < 3 else src[o - 3]
    return LV.block(k, lr[0], lr[1], own)


@pytest.mark.parametrize("o", range(LV.NSRC))
@pytest.mark.parametrize("gain", (0, 1, 96, 127))
def test_every_source_and_gain_bit_exact(o, gain):
    src = _src(o + gain)
    d = B.Dsp()
    knobs = B.panel_knobs(SRC=B.src_knob(o), GAIN=gain, LEV=100)
    for blk in range(3):
        f = B.Frame()
        f.cn(2, B.knobs_words(knobs), blk == 0, track=5)
        got = d.block(f, [2], src)[2]
        want = _want(knobs, src, 5)
        assert np.array_equal(got.view(np.uint32), want.view(np.uint32)), (o, gain, blk)


def test_own_track_is_silent():
    src = _src()
    d = B.Dsp()
    knobs = B.panel_knobs(SRC=B.src_knob(3 + 5))
    f = B.Frame()
    f.cn(2, B.knobs_words(knobs), True, track=5)
    assert not d.block(f, [2], src)[2].any()


def test_untriggered_is_silent():
    d = B.Dsp()
    f = B.Frame()
    f.cn(0, B.knobs_words(B.panel_knobs()), False)
    assert not d.block(f, [0], _src())[0].any()


def test_one_voice_a_track():
    """a second note on the track (another slot) claims it: the first slot goes silent and off (the walk takes
    the newest slot first, so the claim comes before the old voice's block)"""
    src = _src()
    d = B.Dsp()
    w = B.knobs_words(B.panel_knobs(SRC=B.src_knob(1)))
    f = B.Frame()
    f.cn(0, w, True, track=4)
    assert d.block(f, [0], src)[0].any()
    f = B.Frame()
    f.cn(0, w, False, track=4)
    f.cn(1, w, True, track=4)
    out = d.block(f, [1, 0], src)
    assert out[1].any() and not out[0].any()
    f = B.Frame()
    f.cn(0, w, False, track=4)
    f.cn(1, w, False, track=4)
    out = d.block(f, [0, 1], src)
    assert out[1].any() and not out[0].any()


def test_gain_db():
    assert CM.gain_db(0) is None and CM.gain_db(96) == 0 and abs(CM.gain_db(127) - 12.0) < 1e-9


def test_ddr_json_is_the_programs():
    assert ddr.tables_bytes() == P.tables_bytes()
