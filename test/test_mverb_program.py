"""RIFT v0.21: the master reverb's DSP program (run mode) is live.Verb bit for bit: its lines' clearing,
an impulse and noise through every control's range, the controls moving, a NaN input, and a negative
control."""
import numpy as np
import pytest

from dnfw.mverb import live as L
from dnfw.mverb import program as P
from dnfw.perc import machines as PM
from dnfw.perc.dsl import Mem, flt, bits

LY = P.layout()


class Dsp:
    def __init__(self):
        self.frame = {}
        self.mem = Mem(self._read)

    def _read(self, a):
        return self.frame.get(a, 0)

    def block(self, words, x):
        fr = {}
        for k, wv in enumerate(words):              # the frame's halfwords, at FRAME + 2586 + 2k
            a = PM.FRAME + P.FRAME_PRE + 2 * k
            wa = a & ~3
            cur = fr.get(wa, 0)
            cur = (cur & 0xFFFF0000) | wv if not a & 2 else (cur & 0xFFFF) | (wv << 16)
            fr[wa] = cur
        for i, v in enumerate(x):
            fr[P.IN_BUF + 4 * i] = bits(float(v))
        self.frame = fr
        for a in list(fr):
            self.mem.w.pop(a, None)
        p, _ = P.run_block(LY, self._read, self.mem)
        self.steps = p.steps
        l = np.array([flt(self.mem.get(P.OUT_L + 4 * i)) for i in range(32)], np.float32)
        r = np.array([flt(self.mem.get(P.OUT_R + 4 * i)) for i in range(32)], np.float32)
        return l, r


def run(words_of, x_of, blocks, skew=None):
    d, v = Dsp(), L.Verb()
    bad = None
    outs = []
    for b in range(blocks):
        w = words_of(b)
        x = x_of(b)
        gl, gr = d.block(w, x)
        lw = w if skew is None else skew(w)
        wl, wr = v.block(lw, x)
        outs.append(wl)
        if bad is None and not (np.array_equal(gl.view(np.uint32), wl.view(np.uint32))
                                and np.array_equal(gr.view(np.uint32), wr.view(np.uint32))):
            bad = b
    return bad, np.concatenate(outs), d


def noise(seed):
    rs = np.random.RandomState(seed)
    return lambda b: (rs.randn(32) * 0.3).astype(np.float32)


def test_clearing_then_silence_is_exact_and_silent():
    bad, out, _ = run(lambda b: (0x1000, 0x5000, 0x5000, 0x3000), lambda b: np.zeros(32, np.float32), 20)
    assert bad is None and not out.any()


@pytest.mark.parametrize("w", [(0, 0, 0, 0), (0x0100, 0x7F00, 0x7F00, 0x7F00), (0x0400, 0x5000, 0x2000, 0x6000),
                               (0x0200, 0x3F80, 0x3F80, 0x3F80)])
def test_noise_through_the_plate(w):
    bad, out, _ = run(lambda b: w, noise(3), 110)
    assert bad is None, bad
    assert np.abs(out[100 * 32:]).max() > 1e-4


def test_the_longest_pre_delay():
    bad, out, _ = run(lambda b: (0x7F00, 0x7F00, 0x7F00, 0x7F00), noise(4), 40)
    assert bad is None, bad


def test_controls_moving():
    def words(b):
        return tuple((b * 0x0700 * (j + 1)) % 0x7F00 for j in range(4))
    bad, _, _ = run(words, noise(5), 26)
    assert bad is None, bad


def test_a_nan_input_never_reaches_the_lines():
    def x(b):
        a = np.full(32, 0.1, np.float32)
        if b == 18:
            a[3] = np.float32("nan")
            a[7] = np.float32(1e9)
        return a
    bad, out, _ = run(lambda b: (0x800, 0x6000, 0x4000, 0x4000), x, 22)
    assert bad is None and np.isfinite(out).all()


def test_the_comparison_sees_a_wrong_program():
    bad, _, _ = run(lambda b: (0, 0x6000, 0x4000, 0x4000), noise(7), 60,
                    skew=lambda w: (w[0] + 0x100, w[1], w[2], w[3]))
    assert bad is not None


def test_emits():
    text = P.program(LY)
    n = sum(1 for x in text.splitlines() if x.startswith("      ") and not x.strip().startswith("//"))
    print("instructions", n)
    assert 300 < n < 1400 and "JUMP 0xb83715" in text
