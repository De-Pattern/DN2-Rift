"""SMEAR's vocoder jobs (dnfw.smear.program) in run mode equal the float32 contract (live.py),
bit for bit: a whole frame, then the next (prev carried), with the ring's read point moved."""
import struct

import numpy as np

from dnfw.perc.dsl import Mem, Prog
from dnfw.smear import live as LV
from dnfw.smear import program as P

BUFA, TAB, BASE = 0x1000_0000, 0x2000_0000, 0x3000_0000


def u32(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def words(mem, a, n):
    return np.array([mem.get(a + 4 * k) for k in range(n)], np.uint32).view(np.float32)


def setup(buf, pitch, pos, r):
    L = P.Layout(BASE, TAB)
    mem = Mem()
    for k, w in enumerate(P.tables_words()):
        mem.put(TAB + 4 * k, w)
    for k, x in enumerate(buf):
        mem.put(BUFA + 4 * k, u32(x))
    mem.put(L.POS, int(pos))
    mem.put(L.PITCH, u32(pitch))
    mem.put(L.SIZE, len(buf))
    mem.put(L.BASE, BUFA)
    mem.put(L.R, r)
    return L, mem


def test_frames_are_the_contract():
    sr = 48000
    i = np.arange(9000)
    buf = (0.5 * np.sin(2 * np.pi * 440 * i / sr) + 0.3 * np.sin(2 * np.pi * 97 * i / sr)).astype(np.float32)
    v = LV.Voc(buf)
    L, mem = setup(buf, 1.26, 0.0, 0)
    for hop, (tim, pitch, r) in enumerate(((3000.0, 1.26, 0), (3190.0, 0.71, 512), (8900.0, 2.5, 1024), (100.0, 3.9, 1536))):
        size = len(buf)
        spos = LV.HOP * int(np.floor(tim / LV.HOP))
        spos = (spos - 1) % size + 1
        mem.put(L.POS, spos)
        mem.put(L.PITCH, u32(pitch))
        mem.put(L.R, r)
        p = Prog("run", mem=mem)
        P.emit_frame(p, L)
        fr = v.frame(tim, pitch)
        k = (r + np.arange(LV.FFT_N)) & (LV.FFT_N - 1)
        ring = np.zeros(LV.FFT_N, np.float32) if hop == 0 else ring
        ring[k] = ring[k] + fr
        assert words(mem, L.P, LV.FFT_N + 2).tobytes() == np.stack([v.Pr, v.Pi], 1).ravel().tobytes(), hop
        assert words(mem, L.RING, LV.FFT_N).tobytes() == ring.tobytes(), hop
        print(hop, p.steps)


def test_emits():
    p = Prog("emit", prefix="smv")
    P.emit_frame(p, P.Layout(BASE, TAB))
    assert len(p.lines) > 100
