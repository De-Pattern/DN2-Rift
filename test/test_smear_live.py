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
    a, c = y[480 + 8000:n], r[8000:n - 480]      # the frame sounds 15 blocks after its hop starts
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
    # RIFT v0.30 (a tester: "starts at -4.06 but ends at 4", "2 is unselectable"): even ends, every half reached
    assert L.TABLES["SPD"][127] == 4.0 and L.TABLES["SPD"][0] == -4.0 and L.TABLES["SPD"][1] == -4.0
    halves = {float(x) for x in L.TABLES["SPD"]}
    assert all(h / 2 in halves for h in range(-8, 9)), sorted(halves)


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


def test_v024_tune_is_pitch_and_spd_is_speed():
    """v0.24 (owner: "the point of nebulae is that it decouples pitch from speed"): at BLND 0 TUNE (tr)
    transposes PLAY (an octave up: the heads read the ramp twice as fast) while the read point moves at
    SPD alone (the same after the same blocks, whatever the pitch)"""
    buf = np.arange(48000, dtype=np.float32) / 48000.0
    k = dict(L.DEFAULTS, BLND=0)
    slope, where = {}, {}
    for tr in (1.0, 2.0):
        v = L.Voice(buf)
        v.block(k, tr=tr, trig=True)
        y = np.concatenate([v.block(k, tr=tr) for _ in range(10)])
        d = np.diff(y)[5:300]
        slope[tr] = np.median(d)
        where[tr] = (v.pi, v.pf)
    assert abs(slope[2.0] / slope[1.0] - 2.0) < 0.01
    assert where[1.0] == where[2.0]


def test_v024_untransposed_play_reads_the_read_point():
    """v0.24: no transposition at speed 1 (the heads would step as the read point): PLAY is the plain read,
    bit for bit v0.21's"""
    rng = np.random.default_rng(3)
    buf = rng.standard_normal(30000).astype(np.float32) * 0.3
    k = dict(L.DEFAULTS, BLND=64)                    # v0.26: PLAY alone at BLND's middle (BLND 0: the stretch)
    assert L.TABLES["SPD"][k["SPD"]] == np.float32(1)
    v = L.Voice(buf)
    y = np.concatenate([v.block(k, tr=1.0, trig=(n == 0)) for n in range(6)])
    want = buf[:6 * 32] * L.TABLES["PG"][64] * L.TABLES["LEV"][k["LEV"]]
    assert np.array_equal(y, want.astype(np.float32))


def test_v022_freeze_holds_the_read_point_and_sounds():
    """v0.22 FRZ: the read point stops (SPD kept for after), PLAY's share goes to the grains, which go on
    sounding round the held point; FRZ off: as before"""
    rng = np.random.default_rng(1)
    buf = rng.standard_normal(48000).astype(np.float32) * 0.3
    k = dict(L.DEFAULTS, BLND=0)
    v = L.Voice(buf)
    v.block(k, trig=True)
    for _ in range(4):
        v.block(k)
    held = v.pi
    kf = dict(k, FRZ=127)
    ys = [v.block(kf) for _ in range(400)]                         # (DENS 64: a grain about every 134 blocks)
    assert v.pi == held
    assert np.abs(np.concatenate(ys[200:])).max() > 0.01           # the grains go on
    v2 = L.Voice(buf)
    v2.block(dict(k, FRZ=63), trig=True)
    a = v2.block(dict(k, FRZ=63))
    v3 = L.Voice(buf)
    v3.block(k, trig=True)
    assert np.array_equal(a, v3.block(k))                          # under FRZ_ON: unchanged


def test_v026_stretch_transposes_and_keeps_the_speed():
    """v0.26 VOC (owner: SMEAR's vocoder back on heavylight's keyframe stretch): at BLND 0 the stretch plays
    a tone transposed by tr while the read point moves at SPD alone; it splices (KS back under the grain)"""
    sr = 48000
    t = np.arange(sr) / sr
    buf = (0.5 * np.sin(2 * np.pi * 220 * t)).astype(np.float32)
    k = dict(L.DEFAULTS, BLND=0, SPD=72)
    assert L.TABLES["VG"][0] == np.float32(1) and L.TABLES["PG"][0] == 0
    where, freq = {}, {}
    for tr in (1.0, 1.5):
        v = L.Voice(buf)
        y = np.concatenate([v.block(k, tr=tr, trig=(n == 0)) for n in range(1400)])
        seg = y[4000:]
        f = np.abs(np.fft.rfft(seg * np.hanning(len(seg))))
        freq[tr] = np.argmax(f) * sr / len(seg)
        where[tr] = (v.pi, v.pf)
        assert np.all(np.isfinite(y)) and np.max(np.abs(y)) <= 0.5001
    assert where[1.0] == where[1.5]
    assert abs(freq[1.5] / freq[1.0] - 1.5) < 0.02
