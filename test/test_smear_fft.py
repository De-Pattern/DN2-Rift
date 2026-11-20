"""SMEAR phase 0: the FFT program in run mode equals the float32 model bit for bit, and the model
is a correct FFT (against numpy's, float64)."""
import struct

import numpy as np

from dnfw.perc.dsl import Mem, Prog
from dnfw.smear import fft as F

BUF, TAB = 0x1000_0000, 0x2000_0000


def run(prog_fn, words):
    mem = Mem()
    for k, w in enumerate(F.tables_words()):
        mem.put(TAB + 4 * k, w)
    for k, x in enumerate(np.asarray(words, np.float32)):
        mem.put(BUF + 4 * k, struct.unpack("<I", struct.pack("<f", float(x)))[0])
    p = Prog("run", mem=mem)
    prog_fn(p, BUF, TAB)
    out = np.array([mem.get(BUF + 4 * k) for k in range(F.REAL_N)], np.uint32).view(np.float32)
    return out, p.steps


def signal(seed):
    r = np.random.default_rng(seed)
    t = np.arange(F.REAL_N)
    return (0.5 * np.sin(2 * np.pi * 37.3 * t / F.REAL_N) + 0.1 * r.standard_normal(F.REAL_N)).astype(np.float32)


def packed_ref(x):
    X = np.fft.rfft(x.astype(float))
    out = np.empty(F.REAL_N)
    out[0], out[1] = X[0].real, X[F.N].real
    out[2::2], out[3::2] = X[1:F.N].real, X[1:F.N].imag
    return out


def test_forward_model_is_an_fft():
    x = signal(1)
    y = F.forward(x).astype(float)
    ref = packed_ref(x)
    assert np.max(np.abs(y - ref)) < 1e-4 * np.max(np.abs(ref))


def test_inverse_model_round_trips():
    x = signal(2)
    y = F.inverse(F.forward(x)).astype(float) / F.N
    assert np.max(np.abs(y - x)) < 1e-5


def test_forward_program_is_the_model():
    x = signal(3)
    out, steps = run(F.emit_forward, x)
    assert out.tobytes() == F.forward(x).tobytes()
    assert steps < 200_000, steps


def test_inverse_program_is_the_model():
    X = F.forward(signal(4))
    out, steps = run(F.emit_inverse, X)
    assert out.tobytes() == F.inverse(X).tobytes()
    assert steps < 200_000, steps


def test_emits():
    p = Prog("emit", prefix="smf")
    F.emit_forward(p, BUF, TAB)
    F.emit_inverse(p, BUF, TAB)
    assert "JUMP" in p.text()


def test_power_on_tables():
    """emit_init computes, from the 513 QSIN words, every twiddle and the window, word for word."""
    from dnfw.smear import live as LV
    QA, WA = 0x4000_0000, 0x5000_0000
    mem = Mem()
    for k, x in enumerate(F.QSIN):
        mem.put(QA + 4 * k, struct.unpack("<I", struct.pack("<f", float(x)))[0])
    p = Prog("run", mem=mem)
    F.emit_init(p, QA, TAB, WA)
    want = F.tables_words()
    got = [mem.get(TAB + 4 * k) for k in range(F.T_TWF // 4, len(want))]
    assert got == want[F.T_TWF // 4:]
    win = np.array([mem.get(WA + 4 * k) for k in range(F.REAL_N)], np.uint32).view(np.float32)
    assert win.tobytes() == LV.WIN.tobytes()
    print("power-on steps", p.steps)
