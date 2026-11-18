"""SMEAR's vocoder (VOC) as the DSP computes it: the float32 contract (phase 1, first part).

The design and its reference are `model.py` (float64, the pedal's `Mincer`). This module is
what the SHARC program will be held to bit for bit. It follows the same rules as RIFT's
other live models:
- float32 after every operation, in the DSP's order;
- add, subtract, multiply, compare, FLOAT/TRUNC, table reads and integer arithmetic;
- no division and no square root. The reciprocal square root is an integer seed and two
  Newton steps.

**A hop** (512 samples, 16 blocks of 32). At the hop's first block the voice latches:
- the read point `tim` (samples into the buffer);
- the pitch ratio.

The frame is then computed over the hop's 16 blocks, one job a block (`JOBS`), and added
to the overlap-add ring at the end of the hop's last block, so it sounds from the next
block on. In the model the whole frame is computed at that last block. That gives the same
result, because no job reads anything the other blocks change.

The frame:
1. `pos` = the read point, floored to a multiple of HOP and wrapped into (0, size].
2. Two windowed reads of FFT_N samples, at `pos + pitch * i` (F) and HOP x pitch earlier
   (B). Both are linearly interpolated, and B reuses F's fraction (Csound's `mincer` does
   the same).
3. Both are transformed (`fft.forward`, Csound's packing; the Nyquist and DC bins are real).
4. The phase step. `d = conj(B) x prev / |prev|`, then phase-locked (each bin plus its two
   neighbours), normalised, and applied to F: `out = F x u`. `out` is the next `prev`.
5. The inverse (`fft.inverse`, 1024 x the signal). It is windowed and scaled by
   (2/3)/1024: `mincer`'s 4x-overlap scaling with the transform's 1/1024 folded in. It is
   then added into the 2048-sample overlap-add ring, from its read point on.

The output, a sample: the ring's word at the read point, which is then cleared, and the
read point moves on (mod 2048).
"""

from __future__ import annotations

import numpy as np

from . import fft as F

f32 = np.float32
FFT_N = F.REAL_N
HOP = 512
BLOCK = 32
BLOCKS_PER_HOP = HOP // BLOCK            # 16
BINS = FFT_N // 2 + 1                    # 1025
EPS_PREV = f32(1e-30)
EPS_LOCK = f32(1e-15)
SCALE = f32(f32(2.0 / 3.0) * f32(1.0 / 1024.0))
WIN = (f32(0.5) - f32(0.5) * np.cos(2 * np.pi * np.arange(FFT_N) / FFT_N).astype(f32)).astype(f32)


def rsqrt(x: np.ndarray) -> np.ndarray:
    """1 / sqrt(x) for x > 0, float32: the seed 0x5f3759df - (bits >> 1), then two Newton
    steps y = y (1.5 - (0.5 x) y y) in that order."""
    x = np.asarray(x, f32)
    y = (np.uint32(0x5F3759DF) - (x.view(np.uint32) >> np.uint32(1))).astype(np.uint32).view(f32)
    h = f32(0.5) * x
    for _ in range(2):
        t = h * (y * y)
        y = y * (f32(1.5) - t)
    return y


def read_frames(buf: np.ndarray, tim: float, pitch: float):
    """Step 2: the two windowed reads (float32)."""
    size = len(buf)
    spos = HOP * int(np.floor(tim / HOP))
    spos = (spos - 1) % size + 1
    pos = f32(spos)
    p = f32(pitch)
    i = np.arange(FFT_N).astype(f32)
    pf = pos + p * i
    idx = pf.astype(np.int64)                         # TRUNC (pf >= 0)
    frac = pf - idx.astype(f32)
    hp = f32(f32(HOP) * p)
    ib = (pf - hp).astype(np.int64)

    def sample(k):
        k = k % size
        s0 = buf[k]
        s1 = np.where(k + 1 < size, buf[np.minimum(k + 1, size - 1)], s0)
        return s0 + frac * (s1 - s0)
    return sample(idx) * WIN, sample(ib) * WIN


def bins(X: np.ndarray):
    """The packed spectrum as (re, im) of bins 0..1024."""
    re = np.empty(BINS, f32)
    im = np.zeros(BINS, f32)
    re[0], re[-1] = X[0], X[1]
    re[1:-1], im[1:-1] = X[2::2], X[3::2]
    return re, im


def pack(re, im) -> np.ndarray:
    X = np.empty(FFT_N, f32)
    X[0], X[1] = re[0], re[-1]
    X[2::2], X[3::2] = re[1:-1], im[1:-1]
    return X


def phase_step(Fr, Fi, Br, Bi, Pr, Pi):
    """Step 4. Returns the output spectrum (re, im); it is also the next prev."""
    n = rsqrt(Pr * Pr + Pi * Pi + EPS_PREV)
    pr, pi = Pr * n, Pi * n
    dr = Br * pr + Bi * pi
    di = Br * pi - Bi * pr
    lr = dr.copy()
    li = di.copy()
    lr[1:-1] = (dr[:-2] + dr[1:-1]) + dr[2:]
    li[1:-1] = (di[:-2] + di[1:-1]) + di[2:]
    lr[0], li[0] = dr[0] + dr[1], f32(0)
    lr[-1], li[-1] = dr[-2] + dr[-1], f32(0)
    lr = lr + EPS_LOCK
    m = rsqrt(lr * lr + li * li)
    ur, ui = lr * m, li * m
    return Fr * ur - Fi * ui, Fr * ui + Fi * ur


class Voc:
    """One voice's vocoder, block by block."""

    def __init__(self, buf):
        self.buf = np.asarray(buf, f32)
        self.reset()

    def reset(self):
        self.Pr = np.zeros(BINS, f32)
        self.Pi = np.zeros(BINS, f32)
        self.ring = np.zeros(FFT_N, f32)
        self.r = 0
        self.job = 0
        self.latched = (0.0, 1.0)

    def frame(self, tim, pitch):
        fw, bw = read_frames(self.buf, tim, pitch)
        Fr, Fi = bins(F.forward(fw))
        Br, Bi = bins(F.forward(bw))
        Or, Oi = phase_step(Fr, Fi, Br, Bi, self.Pr, self.Pi)
        self.Pr, self.Pi = Or, Oi
        x = F.inverse(pack(Or, Oi))
        return (WIN * x) * SCALE

    def block(self, tim: float, pitch: float) -> np.ndarray:
        """One block of 32 output samples. TIM and PITCH are this block's; only a hop's
        first block's are used."""
        if self.job == 0:
            self.latched = (tim, pitch)
        out = np.empty(BLOCK, f32)
        for s in range(BLOCK):
            out[s] = self.ring[self.r]
            self.ring[self.r] = f32(0)
            self.r = (self.r + 1) & (FFT_N - 1)
        if self.job == BLOCKS_PER_HOP - 1:
            fr = self.frame(*self.latched)
            k = (self.r + np.arange(FFT_N)) & (FFT_N - 1)
            self.ring[k] = self.ring[k] + fr
        self.job = (self.job + 1) % BLOCKS_PER_HOP
        return out
