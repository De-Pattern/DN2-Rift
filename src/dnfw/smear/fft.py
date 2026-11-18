"""SMEAR phase 0: the real 2048-point FFT and its inverse, as one program in the DSL
(`dnfw.perc.dsl`: SHARC assembly, and its exact execution in Python) and as a float32 model
in numpy that computes the same operations in the same order, so the two agree bit for bit.

Layout. A frame is 2048 float32 words. Read as 1024 complex values (re, im) it is the input
of a 1024-point complex FFT:
- radix 2, decimation in time;
- a bit-reversal permutation (a table of swap pairs) first;
- then ten stages of 512 butterflies.

The real split turns the complex result into the 2048-point real transform in Csound's
packing, in place: word 0 holds bin 0, word 1 holds the Nyquist bin, words 2k and 2k+1 hold
bin k (1..1023). The inverse reverses the split and runs the same kernel with the conjugate
twiddles. Its result is 1024 x the signal; the caller folds that 1/1024 into its own scaling.

Every float operation rounds to float32, in the order written here. Products are formed and
rounded before they are added; there is no fused multiply-add.
"""

from __future__ import annotations

import math
import struct

import numpy as np

from ..perc.dsl import Prog, bits
from .addr import at_reg, ldw, stw

N = 1024                       # complex points
REAL_N = 2 * N                 # real points
LOG2N = 10
f32 = np.float32


# ---------------------------------------------------------------------------- tables
def bitrev_pairs() -> list[tuple[int, int]]:
    out = []
    for i in range(N):
        r = int(f"{i:010b}"[::-1], 2)
        if r > i:
            out.append((i, r))
    return out


# One quarter of a sine over a 2048-point circle, float32: the image holds these 513
# words, and every twiddle and the window are derived from them by symmetry at power-on
# (`emit_init`), so the model takes them from here too, word for word.
QSIN = np.sin(2 * np.pi * np.arange(513) / REAL_N).astype(f32)


def cos2048(j: int) -> f32:
    """cos(2 pi j / 2048), j in 0..2047, from QSIN."""
    j &= REAL_N - 1
    q, r = divmod(j, 512)
    z = f32(0)
    return (QSIN[512 - r], z - QSIN[r], z - QSIN[512 - r], QSIN[r])[q]    # 0 - x: the DSP's negation


def sin2048(j: int) -> f32:
    return cos2048(j - 512)


def twiddles(inverse: bool) -> np.ndarray:
    """N/2 complex twiddles of the 1024-point kernel, interleaved: cos, -+sin."""
    w = np.empty(N, f32)
    for k in range(N // 2):
        w[2 * k] = cos2048(2 * k)
        w[2 * k + 1] = sin2048(2 * k) if inverse else f32(0) - sin2048(2 * k)
    return w


def stage_twiddles(tw: np.ndarray) -> np.ndarray:
    """The kernel's twiddles laid out stage by stage: stage s's `half` entries in order
    (entry j is TW[j << (9 - s)]), 1023 complex values in all."""
    out = []
    for s in range(LOG2N):
        for j in range(1 << s):
            t = j << (LOG2N - 1 - s)
            out += [tw[2 * t], tw[2 * t + 1]]
    return np.array(out, f32)


def split_twiddles() -> np.ndarray:
    """The real split's W_2048^k for k = 0..511, interleaved: cos, -sin."""
    w = np.empty(N, f32)
    for k in range(N // 2):
        w[2 * k] = cos2048(k)
        w[2 * k + 1] = f32(0) - sin2048(k)
    return w


PAIRS = bitrev_pairs()            # 496
TW_F, TW_I, TW_S = twiddles(False), twiddles(True), split_twiddles()


def tables_words() -> list[int]:
    """The tables as the DSP holds them, word for word:
    - the swap pairs as byte offsets (a, b), 2 x 496 words;
    - then the stage-ordered TW_F and TW_I (2046 words each) and TW_S (1024)."""
    out = []
    for a, b in PAIRS:
        out += [8 * a, 8 * b]
    for t in (stage_twiddles(TW_F), stage_twiddles(TW_I), TW_S):
        out += [struct.unpack("<I", struct.pack("<f", float(x)))[0] for x in t]
    return out


T_PAIRS = 0
T_TWF = T_PAIRS + 8 * len(PAIRS)
T_TWI = T_TWF + 8 * (N - 1)
T_TWS = T_TWI + 8 * (N - 1)
TABLE_BYTES = T_TWS + 4 * N


class Tabs:
    """Where the transform's tables are: the swap pairs, the forward and inverse stage
    twiddles and the split twiddles, each at its own address (the DSP spreads them over the
    rooms it has, docs/smear.md). An int TABLES means them contiguous in `tables_words`'
    order."""

    def __init__(self, pairs: int, twf: int, twi: int, tws: int):
        self.pairs, self.twf, self.twi, self.tws = pairs, twf, twi, tws


def tabs(tables) -> Tabs:
    if isinstance(tables, Tabs):
        return tables
    return Tabs(tables + T_PAIRS, tables + T_TWF, tables + T_TWI, tables + T_TWS)


# ---------------------------------------------------------------------------- the model
def _cfft(z: np.ndarray, tw: np.ndarray) -> np.ndarray:
    """In place on a float32 array of 2N words (re, im interleaved)."""
    re, im = z[0::2].copy(), z[1::2].copy()
    for a, b in PAIRS:
        re[a], re[b] = re[b], re[a]
        im[a], im[b] = im[b], im[a]
    wr_all, wi_all = tw[0::2], tw[1::2]
    for s in range(LOG2N):
        half = 1 << s
        b = np.arange(N // 2)
        j = b & (half - 1)
        top = ((b - j) << 1) + j
        bot = top + half
        t = j << (LOG2N - 1 - s)
        wr, wi = wr_all[t], wi_all[t]
        ur, ui, vr, vi = re[top], im[top], re[bot], im[bot]
        tr = f32(vr * wr) - f32(vi * wi)
        ti = f32(vr * wi) + f32(vi * wr)
        re[top], im[top] = ur + tr, ui + ti
        re[bot], im[bot] = ur - tr, ui - ti
    z[0::2], z[1::2] = re, im
    return z


def forward(x) -> np.ndarray:
    """2048 real samples -> the packed spectrum (2048 words), float32."""
    z = np.asarray(x, f32).copy()
    _cfft(z, TW_F)
    h = f32(0.5)
    out = z.copy()
    z0r, z0i = z[0], z[1]
    out[0], out[1] = z0r + z0i, z0r - z0i
    out[N], out[N + 1] = z[N], f32(0) - z[N + 1]
    k = np.arange(1, N // 2)
    c = N - k
    ar, ai, br, bi = z[2 * k], z[2 * k + 1], z[2 * c], z[2 * c + 1]
    er, ei = f32(ar + br) * h, f32(ai - bi) * h
    o_r, oi = f32(ai + bi) * h, f32(br - ar) * h
    wr, wi = TW_S[2 * k], TW_S[2 * k + 1]
    tr = f32(o_r * wr) - f32(oi * wi)
    ti = f32(o_r * wi) + f32(oi * wr)
    out[2 * k], out[2 * k + 1] = er + tr, ei + ti
    out[2 * c], out[2 * c + 1] = er - tr, ti - ei
    return out


def inverse(X) -> np.ndarray:
    """The packed spectrum -> 1024 x the 2048 real samples, float32."""
    X = np.asarray(X, f32)
    h = f32(0.5)
    z = X.copy()
    x0, ny = X[0], X[1]
    z[0], z[1] = f32(x0 + ny) * h, f32(x0 - ny) * h
    z[N], z[N + 1] = X[N], f32(0) - X[N + 1]
    k = np.arange(1, N // 2)
    c = N - k
    xr, xi, cr, ci = X[2 * k], X[2 * k + 1], X[2 * c], X[2 * c + 1]
    er, ei = f32(xr + cr) * h, f32(xi - ci) * h
    dr, di = f32(xr - cr) * h, f32(xi + ci) * h
    wr, wi = TW_S[2 * k], TW_S[2 * k + 1]
    o_r = f32(dr * wr) + f32(di * wi)
    oi = f32(di * wr) - f32(dr * wi)
    z[2 * k], z[2 * k + 1] = er - oi, ei + o_r
    z[2 * c], z[2 * c + 1] = er + oi, o_r - ei
    return _cfft(z, TW_I)


# ---------------------------------------------------------------------------- the program
def _bitrev(p: Prog, buf: int, tables: int) -> None:
    p.comment("bit-reversal: swap the pairs in the table")
    p.iconst(8, tabs(tables).pairs)
    p.seti(3, 8)

    def body():
        p.ldpost(8, 3)
        p.ldpost(9, 3)
        at_reg(p, 10, buf)
        p.iop(8, 8, "+", 10)
        p.iop(9, 9, "+", 10)
        p.seti(0, 8)
        p.seti(1, 9)
        p.ldi(0, 0, 0)
        p.ldi(1, 1, 0)
        p.ldi(2, 0, 1)
        p.ldi(3, 1, 1)
        p.sti(0, 0, 2)
        p.sti(1, 0, 3)
        p.sti(0, 1, 0)
        p.sti(1, 1, 1)
    p.loop_r(15, len(PAIRS), body)


def _stages(p: Prog, buf: int, tw: int, stages=range(LOG2N)) -> None:
    """Ten stages; stage s runs N / (2 half) groups of `half` butterflies. Its twiddles are
    the table's own run for that stage (stage_twiddles), read in order, so every pointer
    steps one word at a time."""
    for s in stages:
        half = 1 << s
        off = 8 * (half - 1)                     # stage s's run starts after 1 + 2 + .. + 2^(s-1)
        p.comment(f"stage {s}: {N // (2 * half)} groups of {half} butterflies")
        at_reg(p, 10, buf)

        def group(s=s, half=half, off=off):
            p.seti(0, 10)                            # top
            p.iconst(13, 8 * half)
            p.iop(11, 10, "+", 13)
            p.seti(2, 11)                            # bottom
            p.iop(10, 11, "+", 13)                   # the next group's top
            p.iconst(13, tw + off)
            p.seti(1, 13)

            def bfly():
                p.ldi(0, 0, 0)                       # ur
                p.ldi(1, 1, 0)                       # ui
                p.ldi(2, 0, 2)                       # vr
                p.ldi(3, 1, 2)                       # vi
                p.ldpost(4, 1)                       # wr
                p.ldpost(5, 1)                       # wi
                p.fop(6, 2, "*", 4)
                p.fop(7, 3, "*", 5)
                p.fop(6, 6, "-", 7)                  # tr
                p.fop(7, 2, "*", 5)
                p.fop(8, 3, "*", 4)
                p.fop(7, 7, "+", 8)                  # ti
                p.fop(2, 0, "+", 6)
                p.stpost(0, 2)
                p.fop(2, 1, "+", 7)
                p.stpost(0, 2)
                p.fop(2, 0, "-", 6)
                p.stpost(2, 2)
                p.fop(2, 1, "-", 7)
                p.stpost(2, 2)
            if half == 1:
                bfly()
            else:
                p.loop_r(15, half, bfly)
        p.loop_r(14, N // (2 * half), group)


def _split_loop(p: Prog, buf: int, tables: int, body_math) -> None:
    """k = 1..511 with I0 at bin k, I2 at bin N - k, I1 at W^k."""
    def body():
        p.iconst(12, 1)
        p.iop(14, 15, "-", 12)                       # 510 .. 0
        p.iop(14, 14, "+", 12)                       # k: 511 .. 1
        p.lsh(10, 14, 3)
        at_reg(p, 13, buf)
        p.iop(11, 10, "+", 13)
        p.seti(0, 11)
        p.iconst(13, tabs(tables).tws)
        p.iop(11, 10, "+", 13)
        p.seti(1, 11)
        at_reg(p, 13, buf + 8 * N)
        p.iop(11, 13, "-", 10)
        p.seti(2, 11)
        body_math()
    p.loop_r(15, N // 2 - 1, body)


PARTS = (range(0, 4), range(4, 8), range(8, 10))       # a transform in three jobs


def emit_forward(p: Prog, buf: int, tables: int, part: int | None = None) -> None:
    """The forward transform, or one of its three PARTS (0: the bit reversal and stages
    0..3; 1: stages 4..7; 2: stages 8, 9 and the real split)."""
    if part in (None, 0):
        _bitrev(p, buf, tables)
    for k, st in enumerate(PARTS):
        if part in (None, k):
            _stages(p, buf, tabs(tables).twf, st)
    if part in (None, 2):
        _split_fwd(p, buf, tables)


def _split_fwd(p: Prog, buf: int, tables: int) -> None:
    p.comment("real split")
    ldw(p, 0, buf)
    ldw(p, 1, buf + 4)
    p.fop(2, 0, "+", 1)
    stw(p, buf, 2)
    p.fop(2, 0, "-", 1)
    stw(p, buf + 4, 2)
    p.iconst(3, 0)
    ldw(p, 0, buf + 8 * (N // 2) + 4)
    p.fop(0, 3, "-", 0)          # -im as 0 - im (the model does the same)
    stw(p, buf + 8 * (N // 2) + 4, 0)

    def math_():
        p.fconst(9, 0.5)
        p.ldi(0, 0, 0)                              # ar
        p.ldi(1, 1, 0)                              # ai
        p.ldi(2, 0, 2)                              # br
        p.ldi(3, 1, 2)                              # bi
        p.fop(4, 0, "+", 2)
        p.fop(4, 4, "*", 9)                         # er
        p.fop(5, 1, "-", 3)
        p.fop(5, 5, "*", 9)                         # ei
        p.fop(6, 1, "+", 3)
        p.fop(6, 6, "*", 9)                         # or
        p.fop(7, 2, "-", 0)
        p.fop(7, 7, "*", 9)                         # oi
        p.ldi(0, 0, 1)                              # wr
        p.ldi(1, 1, 1)                              # wi
        p.fop(2, 6, "*", 0)
        p.fop(3, 7, "*", 1)
        p.fop(2, 2, "-", 3)                         # tr
        p.fop(3, 6, "*", 1)
        p.fop(8, 7, "*", 0)
        p.fop(3, 3, "+", 8)                         # ti
        p.fop(0, 4, "+", 2)
        p.sti(0, 0, 0)
        p.fop(0, 5, "+", 3)
        p.sti(1, 0, 0)
        p.fop(0, 4, "-", 2)
        p.sti(0, 2, 0)
        p.fop(0, 3, "-", 5)
        p.sti(1, 2, 0)
    _split_loop(p, buf, tables, math_)


INV_PARTS = (range(0), range(0, 5), range(5, 10))


def emit_inverse(p: Prog, buf: int, tables: int, part: int | None = None) -> None:
    """The inverse, or one of its three parts (0: the split and the bit reversal; 1: stages
    0..4; 2: stages 5..9)."""
    if part in (None, 0):
        _split_inv(p, buf, tables)
        _bitrev(p, buf, tables)
    for k, st in enumerate(INV_PARTS):
        if part in (None, k):
            _stages(p, buf, tabs(tables).twi, st)


def _split_inv(p: Prog, buf: int, tables: int) -> None:
    p.comment("inverse real split")
    p.fconst(9, 0.5)
    ldw(p, 0, buf)
    ldw(p, 1, buf + 4)
    p.fop(2, 0, "+", 1)
    p.fop(2, 2, "*", 9)
    stw(p, buf, 2)
    p.fop(2, 0, "-", 1)
    p.fop(2, 2, "*", 9)
    stw(p, buf + 4, 2)
    p.iconst(3, 0)
    ldw(p, 0, buf + 8 * (N // 2) + 4)
    p.fop(0, 3, "-", 0)
    stw(p, buf + 8 * (N // 2) + 4, 0)

    def math_():
        p.fconst(9, 0.5)
        p.ldi(0, 0, 0)                              # xr
        p.ldi(1, 1, 0)                              # xi
        p.ldi(2, 0, 2)                              # cr
        p.ldi(3, 1, 2)                              # ci
        p.fop(4, 0, "+", 2)
        p.fop(4, 4, "*", 9)                         # er
        p.fop(5, 1, "-", 3)
        p.fop(5, 5, "*", 9)                         # ei
        p.fop(6, 0, "-", 2)
        p.fop(6, 6, "*", 9)                         # dr
        p.fop(7, 1, "+", 3)
        p.fop(7, 7, "*", 9)                         # di
        p.ldi(0, 0, 1)                              # wr
        p.ldi(1, 1, 1)                              # wi
        p.fop(2, 6, "*", 0)
        p.fop(3, 7, "*", 1)
        p.fop(2, 2, "+", 3)                         # or
        p.fop(3, 7, "*", 0)
        p.fop(8, 6, "*", 1)
        p.fop(3, 3, "-", 8)                         # oi
        p.fop(0, 4, "-", 3)
        p.sti(0, 0, 0)
        p.fop(0, 5, "+", 2)
        p.sti(1, 0, 0)
        p.fop(0, 4, "+", 3)
        p.sti(0, 2, 0)
        p.fop(0, 2, "-", 5)
        p.sti(1, 2, 0)
    _split_loop(p, buf, tables, math_)


# ---------------------------------------------------------------------------- power-on
def emit_cos(p: Prog, d: int, j: int, qsin: int) -> None:
    """Fd = cos2048(Rj) (Rj in R8..R15, kept). Clobbers R0..R3, R12, R13 and I3."""
    p.iconst(12, REAL_N - 1)
    p.iop(0, j, "AND", 12)
    p.lsh(1, 0, -9)                               # q
    p.iconst(12, 511)
    p.iop(2, 0, "AND", 12)                        # r
    p.iconst(13, 512)
    p.iop(3, 13, "-", 2)                          # 512 - r
    p.iconst(12, 1)
    p.iop(12, 12, "AND", 1)                       # q odd: Q[r], else Q[512 - r]
    p.ifz(12, "NE", lambda: p.ipass(3, 2))
    p.lsh(3, 3, 2)
    p.iconst(13, qsin)
    p.iop(3, 13, "+", 3)
    p.seti(3, 3)
    p.ldi(d, 0, 3)
    # negative in quadrants 1 and 2: (q + 1) & 2
    p.iconst(12, 1)
    p.iop(13, 12, "+", 1)
    p.iconst(12, 2)
    p.iop(13, 13, "AND", 12)
    p.ifz(13, "NE", lambda: (p.iconst(12, 0), p.fop(d, 12, "-", d)))


def emit_init(p: Prog, qsin: int, tables: int, win: int) -> None:
    """The tables `tables_words` and live.WIN describe, computed from QSIN (513 words at
    QSIN) into TABLES (after the swap pairs, which the image holds) and WIN."""
    def table(dst: int, n: int, jof, store):
        """for i in 0..n-1: store(i) with R14 = i; I5 walks DST."""
        p.iconst(9, dst)
        p.seti(5, 9)
        p.iconst(14, 0)

        def body():
            jof()
            store()
            p.iconst(12, 1)
            p.iop(14, 14, "+", 12)
        p.loop_r(15, n, body)

    def cs(sign_sin: bool, shift_j):
        """store cos(J), then +-sin(J) (J in R11)."""
        def st():
            emit_cos(p, 4, 11, qsin)
            p.stpost(5, 4)
            p.iconst(12, -512)
            p.iop(10, 11, "+", 12)
            emit_cos(p, 4, 10, qsin)              # sin(J) = cos(J - 512)
            if sign_sin:
                p.iconst(12, 0)
                p.fop(4, 12, "-", 4)
            p.stpost(5, 4)
        return st

    T = tabs(tables)
    for base, neg in ((T.twf, True), (T.twi, False)):
        p.comment(f"power-on: the {'forward' if neg else 'inverse'} stage twiddles")
        off = 0
        for s in range(LOG2N):
            half = 1 << s
            dst = base + 8 * (half - 1)
            table(dst, half, lambda s=s: p.lsh(11, 14, LOG2N - s), cs(neg, None))   # J = 2 (j << (9 - s))
    p.comment("power-on: the split twiddles")
    table(T.tws, N // 2, lambda: p.ipass(11, 14), cs(True, None))
    p.comment("power-on: the Hann window")

    def hann():
        emit_cos(p, 4, 11, qsin)
        p.fconst(6, 0.5)
        p.fop(4, 6, "*", 4)
        p.fop(4, 6, "-", 4)
        p.stpost(5, 4)
    table(win, REAL_N, lambda: p.ipass(11, 14), hann)
