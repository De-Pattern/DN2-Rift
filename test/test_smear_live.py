"""SMEAR's float32 vocoder contract (dnfw.smear.live) against its float64 design (model.Mincer)."""
import numpy as np

from dnfw.smear import live as L
from dnfw.smear import model as M

SR = 48000


def _src():
    i = np.arange(SR * 2)
    return (0.5 * np.sin(2 * np.pi * 440 * i / SR) + 0.2 * np.sin(2 * np.pi * 1234.5 * i / SR)).astype(np.float32)


def test_rsqrt():
    x = np.logspace(-30, 20, 2000).astype(np.float32)
    y = L.rsqrt(x).astype(float)
    assert np.max(np.abs(y * np.sqrt(x.astype(float)) - 1)) < 5e-6


def test_voc_matches_the_design_one_hop_later():
    b = _src()
    n = SR // 2
    tim = 0.1 * SR + 0.37 * np.arange(n + 4096)
    v = L.Voc(b)
    y = np.concatenate([v.block(tim[s], 1.26) for s in range(0, n, 32)]).astype(float)
    m = M.Mincer()
    r = np.concatenate([m.process(b.astype(float), tim[s:s + 32], 1.26, 32) for s in range(0, n, 32)])
    a, c = y[512 + 8000:n], r[8000:n - 512]
    snr = 10 * np.log10((c ** 2).sum() / ((a - c) ** 2).sum())
    assert snr > 40, snr


def test_freeze_holds_level():
    b = _src()
    v = L.Voc(b)
    y = np.concatenate([v.block(20000.0, 1.0) for _ in range(SR // 32)]).astype(float)
    tail = y[SR // 2:]
    rms = np.sqrt(np.mean(tail ** 2))
    assert 0.25 < rms < 0.5, rms
    assert np.all(np.isfinite(y))


def test_voice_speed_table_detents():
    assert L.TABLES["SPD"][64] == 0.0
    assert L.TABLES["SPD"][80] == 1.0 and L.TABLES["SPD"][48] == -1.0
    assert L.TABLES["SPD"][127] == 4.0 and L.TABLES["SPD"][0] < -4.0


def test_voice_paths_finite_and_frozen_holds():
    b = _src()
    for blnd in (0, 64, 127):
        k = dict(L.DEFAULTS, SPD=64, BLND=blnd, STRT=30, SIZE=90, DENS=90, OVLP=110)
        v = L.Voice(b)
        y = np.concatenate([v.block(k, 2 ** (7 / 12), trig=(n == 0), clock=n) for n in range(600)]).astype(float)
        assert np.all(np.isfinite(y)) and np.max(np.abs(y)) < 2.0
        assert v.pi == v.loop(k)[0]                 # SPD 64: the read point never moved


def test_recip():
    for x in (1.0, 48.0, 1234.5, 384000.0):
        assert abs(float(L.recip(x)) * x - 1) < 1e-6


def test_lanes_steal_the_oldest():
    ln = L.Lanes()
    a, b, c = object(), object(), object()
    assert ln.take(a) == 0 and ln.take(b) == 1
    assert ln.take(c) == 0 and ln.held(a) is None and ln.held(c) == 0
    ln.free(b)
    assert ln.take(a) == 1
