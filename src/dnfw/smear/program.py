"""SMEAR's vocoder jobs in the DSL (dnfw.perc.dsl): each the same operations, in the same
order, as `live.py`, so the run mode equals the float32 contract bit for bit
(test_smear_program.py).

The jobs of a frame, and what each reads and writes (all in a `Layout`):
- `emit_read(B=False)`: the windowed read F (or B) from the buffer into WF (or WB).
- `fft.emit_forward` on WF and on WB.
- `emit_phase`: from WF, WB and P, the output spectrum. It goes into WF (packed) and P;
  D is its scratch.
- `fft.emit_inverse` on WF.
- `emit_ola`: WF windowed and scaled, added into RING from its read point R.

Where these sit (L1, L2, DDR), and how they are cut into a block's jobs, is the layout's
business (docs/smear.md, the memory plan); the code does not change with it.
"""

from __future__ import annotations

import struct

import numpy as np

from ..perc.dsl import Prog
from . import fft as FT
from . import live as LV
from .addr import At, at_reg, ldw, stw

N = LV.FFT_N
MAGIC = 0x5F3759DF


class Layout:
    """Byte addresses. Params (fixed words, which the voice writes before a job): POS (int:
    spos), PITCH (float), SIZE (int), BASE (the buffer's first sample), R (the ring's read
    point, int), CNT, FMT. D, the phase step's scratch, is fixed too.

    WF, WB, P and RING are fixed (LANE None) or a lane's: LANE = (word of the lane's
    L2 base, word of its DDR base). WF and WB then sit at the L2 base, P and RING at the
    DDR one (`At`), so one copy of the code serves both lanes."""

    def __init__(self, base: int, tables: int, lane: tuple[int, int] | None = None,
                 win: int | None = None, fft=None):
        a = base
        self.POS, self.PITCH, self.SIZE, self.BASE, self.R, self.CNT, self.FMT, self.FRAME = (a + 4 * k for k in range(8))
        a += 64
        self.D = a; a += 4 * (N + 2)
        if lane is None:
            self.WF = a; a += 4 * N
            self.WB = a; a += 4 * N
            self.P = a; a += 4 * (N + 2)
            self.RING = a; a += 4 * N
        else:
            self.WF, self.WB = At(lane[0], 0), At(lane[0], 4 * N)
            self.P, self.RING = At(lane[1], 0), At(lane[1], 4 * (N + 2))
        self.end = a
        self.WIN = tables if win is None else win                 # the Hann window
        self.FFT = tables + 4 * N if fft is None else fft         # an fft.Tabs, or contiguous


LANE_L2_BYTES = 8 * N                     # WF, WB
LANE_DDR_BYTES = 4 * (N + 2) + 4 * N      # P, RING


def tables_words() -> list[int]:
    w = [struct.unpack("<I", struct.pack("<f", float(x)))[0] for x in LV.WIN]
    return w + FT.tables_words()


# ---------------------------------------------------------------------------- helpers
def rsqrt(p: Prog, d: int, x: int, t1: int, t2: int, t3: int) -> None:
    """Fd = rsqrt(Fx) as live.rsqrt. Clobbers t1..t3 (all distinct from d and x)."""
    p.lsh(t1, x, -1)
    p.iconst(t2, MAGIC)
    p.iop(d, t2, "-", t1)
    p.fconst(t3, 0.5)
    p.fop(t3, t3, "*", x)                       # h
    for _ in range(2):
        p.fop(t1, d, "*", d)
        p.fop(t1, t3, "*", t1)
        p.fconst(t2, 1.5)
        p.fop(t1, t2, "-", t1)
        p.fop(d, d, "*", t1)


def wrap(p: Prog, r: int, size: int) -> None:
    """Rr into 0..size-1 by repeated adds or subtracts (Python's r % size)."""
    if p.run:
        while True:
            p.e("COMP")
            if p._cmp(r, size, "i") >= 0:
                p.iop(r, r, "-", size)
                continue
            p.e("PASS")
            if p.r[r] >> 31:
                p.iop(r, size, "+", r)
                continue
            break
        return
    top, up, done = p.label("wrap"), p.label("wrapup"), p.label("wrapped")
    p.place(top)
    p.e(f"COMP(R{r}, R{size});")
    p.jump("LT", up)
    p.iop(r, r, "-", size)
    p.jump("", top)
    p.place(up)
    p.e(f"R{r} = PASS R{r};")
    p.jump("GE", done)
    p.iop(r, size, "+", r)
    p.jump("", up)
    p.place(done)


def fetch(p: Prog, d: int, k: int, base: int, fmt: int, t: int, ii: int) -> None:
    """Fd = sample Rk of the buffer at Rbase: a float32, or (the word at FMT nonzero) an
    int16 / 32768 read as the half of its 32-bit word, as the sampler's `fetch`. BASE and T
    are R8..R15 and distinct; clobbers Rt, R12 and I`ii`."""
    def f32_():
        p.lsh(12, k, 2)
        p.iop(12, base, "+", 12)
        p.seti(ii, 12)
        p.ldi(d, 0, ii)

    def i16():
        p.lsh(12, k, 1)
        p.iop(t, base, "+", 12)                 # the frame's byte address
        p.iconst(12, -4)
        p.iop(12, t, "AND", 12)
        p.seti(ii, 12)
        p.ldi(d, 0, ii)
        p.iconst(12, 2)
        p.iop(t, t, "AND", 12)
        p.ifz(t, "EQ", lambda: p.lsh(d, d, 16))
        p.iconst(12, 0xFFFF0000 - (1 << 32))
        p.iop(d, d, "AND", 12)
        p.iconst(12, -31)
        p.float_(d, d, 12)
    p.ld(12, fmt)
    p.ifz(12, "NE", i16, f32_)


# ---------------------------------------------------------------------------- the jobs
def emit_read(p: Prog, L: Layout, B: bool = False, half: int | None = None) -> None:
    """WF (WB): sample(spos + offset) x WIN for i = 0..N-1, as live.read_frames, or one HALF
    of it (0: i < 1024, 1: the rest). POS holds spos as an integer."""
    i0, n = (0, N) if half is None else (half * N // 2, N // 2)
    p.comment(f"SMEAR read {'B' if B else 'F'}")
    p.ld(10, L.POS)
    p.ld(9, L.PITCH)
    p.ld(13, L.SIZE)
    p.ld(14, L.BASE)
    p.fconst(8, float(LV.HOP))
    p.fop(8, 8, "*", 9)                          # hp
    p.iconst(11, i0)
    p.iconst(12, 0)
    p.float_(11, 11, 12)                         # fi = i0 (FLOAT i0 BY 0)
    p.iconst(0, L.WIN + 4 * i0)
    p.seti(4, 0)
    at_reg(p, 0, (L.WB if B else L.WF) + 4 * i0)
    p.seti(5, 0)

    def body():
        p.fop(0, 9, "*", 11)                     # x
        p.trunc(2, 0)
        p.iconst(3, 0)
        p.float_(4, 2, 3)
        p.fop(5, 0, "-", 4)                      # frac
        if B:
            p.fop(1, 0, "-", 8)                  # xb
            p.trunc(2, 1)
            p.float_(4, 2, 3)
            p.if_(4, "GT", 1, lambda: (p.iconst(12, 1), p.iop(2, 2, "-", 12)))   # floor
        p.iop(2, 10, "+", 2)                     # spos + offset
        wrap(p, 2, 13)
        fetch(p, 6, 2, 14, L.FMT, 9, 0)          # s0 (R9: the pitch is in F9 ...
        p.ld(9, L.PITCH)                                        # ... so it is reloaded)
        p.iconst(12, 1)
        p.iop(3, 12, "+", 2)
        p.fpass(7, 6)                            # s1 = s0 at the end ...
        p.if_(3, "LT", 13, lambda: (fetch(p, 7, 3, 14, L.FMT, 9, 0), p.ld(9, L.PITCH)),
              kind="i")                          # ... else the next sample
        p.fop(7, 7, "-", 6)
        p.fop(7, 5, "*", 7)
        p.fop(7, 6, "+", 7)                      # s0 + frac (s1 - s0)
        p.ldpost(6, 4)
        p.fop(7, 7, "*", 6)
        p.stpost(5, 7)
        p.fconst(6, 1.0)
        p.fop(11, 11, "+", 6)
    p.loop_r(15, n, body)


def _bin1(p: Prog) -> None:
    """d from Pr F0, Pi F1, Br F2, Bi F3 -> dr F4, di F5 (uses F6..F10, R7, R8)."""
    p.fop(4, 0, "*", 0)
    p.fop(5, 1, "*", 1)
    p.fop(4, 4, "+", 5)
    p.fconst(5, float(LV.EPS_PREV))
    p.fop(4, 4, "+", 5)
    rsqrt(p, 6, 4, 7, 8, 10)
    p.fop(0, 0, "*", 6)                          # pr
    p.fop(1, 1, "*", 6)                          # pi
    p.fop(4, 2, "*", 0)
    p.fop(5, 3, "*", 1)
    p.fop(4, 4, "+", 5)                          # dr
    p.fop(5, 2, "*", 1)
    p.fop(6, 3, "*", 0)
    p.fop(5, 5, "-", 6)                          # di


def _bin2(p: Prog) -> None:
    """From lr F4, li F5 and Fr F0, Fi F1: Or F2, Oi F3 (uses F6..F10, R7, R8)."""
    p.fconst(6, float(LV.EPS_LOCK))
    p.fop(4, 4, "+", 6)
    p.fop(6, 4, "*", 4)
    p.fop(9, 5, "*", 5)
    p.fop(6, 6, "+", 9)
    rsqrt(p, 9, 6, 7, 8, 10)
    p.fop(4, 4, "*", 9)                          # ur
    p.fop(5, 5, "*", 9)                          # ui
    p.fop(2, 0, "*", 4)
    p.fop(6, 1, "*", 5)
    p.fop(2, 2, "-", 6)                          # Or
    p.fop(3, 0, "*", 5)
    p.fop(6, 1, "*", 4)
    p.fop(3, 3, "+", 6)                          # Oi


def emit_phase(p: Prog, L: Layout) -> None:
    """live.phase_step on WF, WB and P; the result into WF (packed) and P."""
    p.comment("SMEAR phase step, pass 1: d into D")
    for (pw, bw, dw) in ((0, 0, 0), (N, 1, N)):  # DC, then Nyquist (real; their im are 0)
        ldw(p, 0, L.P + 4 * pw)
        ldw(p, 1, L.P + 4 * pw + 4)
        ldw(p, 2, L.WB + 4 * bw)
        p.iconst(3, 0)
        _bin1(p)
        p.st(L.D + 4 * dw, 4)
        p.st(L.D + 4 * dw + 4, 5)
    for i, a in ((1, L.P + 8), (2, L.WB + 8), (3, L.D + 8)):
        at_reg(p, 9, a)
        p.seti(i, 9)

    def pass1():
        p.ldpost(0, 1)
        p.ldpost(1, 1)
        p.ldpost(2, 2)
        p.ldpost(3, 2)
        _bin1(p)
        p.stpost(3, 4)
        p.stpost(3, 5)
    p.loop_r(15, N // 2 - 1, pass1)

    p.comment("pass 2: lock, normalise, apply to F")
    p.ld(4, L.D)
    p.ld(6, L.D + 8)
    p.fop(4, 4, "+", 6)                          # lr0 = d0r + d1r
    p.iconst(5, 0)                               # li0 = 0
    ldw(p, 0, L.WF)
    p.iconst(1, 0)
    _bin2(p)
    stw(p, L.WF, 2)
    stw(p, L.P, 2)
    p.iconst(3, 0)
    stw(p, L.P + 4, 3)
    p.ld(4, L.D + 4 * (N - 2))
    p.ld(6, L.D + 4 * N)
    p.fop(4, 4, "+", 6)                          # lrN = d1023r + d1024r
    p.iconst(5, 0)
    ldw(p, 0, L.WF + 4)
    p.iconst(1, 0)
    _bin2(p)
    stw(p, L.WF + 4, 2)
    stw(p, L.P + 4 * N, 2)
    p.iconst(3, 0)
    stw(p, L.P + 4 * N + 4, 3)
    for i, a in ((0, L.WF + 8), (1, L.P + 8), (3, L.D)):
        at_reg(p, 9, a)
        p.seti(i, 9)

    def pass2():
        p.ldpost(4, 3)                           # d[k-1]
        p.ldpost(5, 3)
        p.ldi(6, 0, 3)                           # d[k]
        p.fop(4, 4, "+", 6)
        p.ldi(6, 1, 3)
        p.fop(5, 5, "+", 6)
        p.ldi(6, 2, 3)                           # d[k+1]
        p.fop(4, 4, "+", 6)
        p.ldi(6, 3, 3)
        p.fop(5, 5, "+", 6)
        p.ldi(0, 0, 0)
        p.ldi(1, 1, 0)
        _bin2(p)
        p.stpost(0, 2)
        p.stpost(0, 3)
        p.stpost(1, 2)
        p.stpost(1, 3)
    p.loop_r(15, N // 2 - 1, pass2)


def emit_ola(p: Prog, L: Layout) -> None:
    """RING[(R + i) & 2047] += (WIN[i] x WF[i]) x SCALE, as live.Voc.block."""
    p.comment("SMEAR overlap-add")
    p.ld(13, L.R)
    at_reg(p, 14, L.RING)
    p.iconst(0, L.WIN)
    p.seti(4, 0)
    at_reg(p, 0, L.WF)
    p.seti(5, 0)
    p.fconst(9, float(LV.SCALE))

    def body():
        p.ldpost(0, 4)
        p.ldpost(1, 5)
        p.fop(0, 0, "*", 1)
        p.fop(0, 0, "*", 9)
        p.lsh(3, 13, 2)
        p.iop(3, 14, "+", 3)
        p.seti(0, 3)
        p.ldi(1, 0, 0)
        p.fop(1, 1, "+", 0)
        p.sti(0, 0, 1)
        p.iconst(12, 1)
        p.iop(13, 13, "+", 12)
        p.iconst(12, N - 1)
        p.iop(13, 13, "AND", 12)
    p.loop_r(15, N, body)


def emit_frame(p: Prog, L: Layout) -> None:
    """A whole frame in one go (the test's composition; the DSP cuts it into jobs)."""
    emit_read(p, L, False)
    emit_read(p, L, True)
    FT.emit_forward(p, L.WF, L.FFT)
    FT.emit_forward(p, L.WB, L.FFT)
    emit_phase(p, L)
    FT.emit_inverse(p, L.WF, L.FFT)
    emit_ola(p, L)


# ================================================================================ GRN
class GLayout:
    """The grains' words (byte addresses). Inputs a block: READ (int), PITCH, GINC, ENVINC,
    SPRAY, PRAND (floats), WINP (the window table's address), SIZE (int), BASE (the
    buffer's address). State: GPH, RNG, ORD, MS, GAIN, then GRAINS x 8 words: on, pi, pf,
    di, df, e, ei, o. OUT: the block's 32 samples. CNT: a loop counter."""

    NAMES = ("READ", "PITCH", "GINC", "ENVINC", "SPRAY", "PRAND", "WINP", "SIZE", "BASE",
             "GPH", "RNG", "ORD", "MS", "GAIN", "CNT", "FMT")

    def __init__(self, base: int):
        for k, n in enumerate(self.NAMES):
            setattr(self, n, base + 4 * k)
        self.G = base + 64
        self.OUT = self.G + 32 * LV.GRAINS
        self.end = self.OUT + 4 * 32


def _rnd(p: Prog, G: GLayout, d: int) -> None:
    """Fd = the generator's next value (uses R8, R13)."""
    p.ld(8, G.RNG)
    p.iconst(13, LV.LCG_A)
    p.mul_ssi(8, 8, 13)
    p.iconst(13, LV.LCG_C)
    p.iop(8, 13, "+", 8)
    p.st(G.RNG, 8)
    p.iconst(13, -31)
    p.float_(d, 8, 13)


def _launch(p: Prog, G: GLayout) -> None:
    p.comment("a grain: the first free slot, else the oldest")
    p.iconst(9, -1)
    for k in reversed(range(LV.GRAINS)):
        p.ld(0, G.G + 32 * k)
        p.ifz(0, "EQ", lambda k=k: p.iconst(9, k))

    def oldest():
        p.iconst(9, 0)
        p.ld(11, G.G + 28)
        for k in range(1, LV.GRAINS):
            p.ld(10, G.G + 32 * k + 28)
            p.if_(10, "LT", 11, lambda k=k: (p.iconst(9, k), p.ipass(11, 10)), kind="i")
    p.ifz(9, "LT", oldest)
    p.lsh(9, 9, 5)
    p.iconst(10, G.G)
    p.iop(9, 10, "+", 9)
    p.seti(1, 9)
    # the position
    _rnd(p, G, 0)
    p.ld(1, G.SPRAY)
    p.fop(0, 0, "*", 1)
    p.ld(10, G.SIZE)
    p.iconst(13, 0)
    p.float_(1, 10, 13)
    p.fop(0, 0, "*", 1)
    p.trunc(2, 0)
    p.ld(9, G.READ)
    p.iop(2, 9, "+", 2)
    wrap(p, 2, 10)
    p.sti(1, 1, 2)                                # pi
    # the step
    _rnd(p, G, 0)
    p.ld(1, G.PRAND)
    p.fop(0, 0, "*", 1)
    p.fconst(1, 0.1)
    p.fop(0, 0, "*", 1)                           # x
    c1, c2, c3 = (float(c) for c in LV.LN2)
    p.fconst(1, c3)
    p.fop(1, 0, "*", 1)
    p.fconst(2, c2)
    p.fop(1, 2, "+", 1)
    p.fop(1, 0, "*", 1)
    p.fconst(2, c1)
    p.fop(1, 2, "+", 1)
    p.fop(1, 0, "*", 1)
    p.fconst(2, 1.0)
    p.fop(1, 2, "+", 1)                           # 2^x
    p.ld(0, G.PITCH)
    p.fop(0, 0, "*", 1)                           # step
    p.trunc(2, 0)
    p.sti(3, 1, 2)                                # di
    p.iconst(3, 0)
    p.float_(1, 2, 3)
    p.fop(0, 0, "-", 1)
    p.sti(4, 1, 0)                                # df
    p.iconst(0, 0)
    p.sti(2, 1, 0)                                # pf = 0.0
    p.sti(5, 1, 0)                                # e = 0.0
    p.ld(0, G.ENVINC)
    p.sti(6, 1, 0)                                # ei
    p.ld(9, G.ORD)
    p.iconst(12, 1)
    p.iop(9, 9, "+", 12)
    p.st(G.ORD, 9)
    p.sti(7, 1, 9)                                # o
    p.iconst(0, 1)
    p.sti(0, 1, 0)                                # on


def _grain(p: Prog, G: GLayout) -> None:
    """The grain at I1 (R14): its sample into F11 (the sum), then it moves on."""
    def render():
        p.ldi(8, 1, 1)                            # pi
        p.ld(9, G.BASE)
        p.iconst(12, 1)
        p.iop(3, 12, "+", 8)
        p.if_(3, "GE", 13, lambda: p.iconst(3, 0), kind="i")
        fetch(p, 4, 8, 9, G.FMT, 10, 2)              # s0
        fetch(p, 5, 3, 9, G.FMT, 10, 2)              # s1
        p.fop(5, 5, "-", 4)
        p.ldi(6, 2, 1)                            # pf
        p.fop(5, 6, "*", 5)
        p.fop(5, 4, "+", 5)                       # v
        p.fconst(6, float(LV.WIN_LEN))
        p.fop(6, 1, "*", 6)                       # x = e 512
        p.trunc(2, 6)
        p.iconst(3, 0)
        p.float_(7, 2, 3)
        p.fop(6, 6, "-", 7)                       # ef
        p.ld(10, G.WINP)
        p.lsh(3, 2, 2)
        p.iop(3, 10, "+", 3)
        p.seti(0, 3)
        p.ldi(7, 0, 0)                            # w0
        p.ldi(4, 1, 0)
        p.fop(4, 4, "-", 7)
        p.fop(4, 6, "*", 4)
        p.fop(4, 7, "+", 4)                       # w
        p.fconst(6, float(LV.GRAIN_AMP))
        p.fop(5, 5, "*", 6)
        p.fop(5, 5, "*", 4)
        p.fop(11, 11, "+", 5)
        p.ldi(6, 2, 1)
        p.ldi(7, 4, 1)
        p.fop(6, 6, "+", 7)                       # pf + df
        p.ldi(3, 3, 1)
        p.iop(3, 8, "+", 3)                       # pi + di
        p.fconst(7, 1.0)
        p.if_(6, "GE", 7, lambda: (p.fop(6, 6, "-", 7), p.iconst(12, 1), p.iop(3, 12, "+", 3)))
        p.if_(3, "GE", 13, lambda: p.iop(3, 3, "-", 13), kind="i")
        p.sti(2, 1, 6)
        p.sti(1, 1, 3)
        p.ldi(7, 6, 1)
        p.fop(1, 1, "+", 7)
        p.sti(5, 1, 1)                            # e + ei

    def live_():
        p.ldi(1, 5, 1)                            # e
        p.fconst(2, 1.0)
        p.if_(1, "GE", 2, lambda: (p.iconst(0, 0), p.sti(0, 1, 0)), render)
    p.ldi(0, 0, 1)
    p.ifz(0, "NE", live_)


def emit_grn(p: Prog, G: GLayout) -> None:
    """live.Grn.block: 32 samples into OUT."""
    p.comment("SMEAR grains")
    p.iconst(0, G.OUT)
    p.seti(5, 0)

    def sample():
        p.ld(0, G.GPH)
        p.ld(1, G.GINC)
        p.fop(0, 0, "+", 1)
        p.fconst(1, 1.0)

        def passed():
            p.fop(0, 0, "-", 1)
            p.st(G.GPH, 0)
            p.ld(0, G.ENVINC)
            p.iconst(1, 0)
            p.if_(0, "GT", 1, lambda: _launch(p, G))
        p.if_(0, "GE", 1, passed, lambda: p.st(G.GPH, 0))
        p.ld(13, G.SIZE)
        p.iconst(11, 0)                           # the sum: 0.0
        p.iconst(14, G.G)

        def one():
            p.seti(1, 14)
            _grain(p, G)
            p.iconst(12, 32)
            p.iop(14, 14, "+", 12)
        p.loop_r(15, LV.GRAINS, one)
        p.stpost(5, 11)
    p.loop(G.CNT, 32, sample)

    p.comment("the limiter")
    p.ld(0, G.MS)
    p.iconst(9, G.OUT)
    p.seti(5, 9)
    p.fconst(2, float(LV.RMS_B))
    p.fconst(3, float(LV.RMS_C))

    def ms():
        p.ldpost(1, 5)
        p.fop(1, 1, "*", 1)
        p.fop(1, 3, "*", 1)
        p.fop(4, 2, "*", 0)
        p.fop(0, 4, "+", 1)
    p.loop_r(15, 32, ms)
    p.st(G.MS, 0)
    p.fconst(1, float(LV.EPS_PREV))
    p.fop(0, 0, "+", 1)
    rsqrt(p, 4, 0, 7, 8, 10)
    p.fconst(1, float(LV.RMS_CEIL))
    p.fop(4, 1, "*", 4)
    p.fconst(1, 1.0)
    p.fop(4, 4, "MIN", 1)                         # gn
    p.ld(5, G.GAIN)
    p.st(G.GAIN, 4)
    p.fop(4, 4, "-", 5)
    p.fconst(1, 1.0 / 32)
    p.fop(4, 4, "*", 1)                           # dg
    p.iconst(9, G.OUT)
    p.seti(5, 9)

    def ramp():
        p.fop(5, 5, "+", 4)
        p.ldi(0, 0, 5)
        p.fop(0, 0, "*", 5)
        p.stpost(5, 0)
    p.loop_r(15, 32, ramp)


# ================================================================================ the jobs of a hop
def _jobs(L: Layout):
    return (
        lambda p: emit_read(p, L, False, 0),
        lambda p: emit_read(p, L, False, 1),
        lambda p: emit_read(p, L, True, 0),
        lambda p: emit_read(p, L, True, 1),
        lambda p: _fwd(p, L, L.WF, 0),
        lambda p: _fwd(p, L, L.WF, 1),
        lambda p: _fwd(p, L, L.WF, 2),
        lambda p: _fwd(p, L, L.WB, 0),
        lambda p: _fwd(p, L, L.WB, 1),
        lambda p: _fwd(p, L, L.WB, 2),
        lambda p: emit_phase(p, L),
        lambda p: FT.emit_inverse(p, L.WF, L.FFT, 0),
        lambda p: FT.emit_inverse(p, L.WF, L.FFT, 1),
        lambda p: FT.emit_inverse(p, L.WF, L.FFT, 2),
        lambda p: emit_ola(p, L),
    )


def _fwd(p: Prog, L: Layout, frame, part: int) -> None:
    """A part of the forward transform on FRAME (WF or WB): one copy of the code, a leaf
    subroutine, finding its frame from the word L.FRAME."""
    at_reg(p, 9, frame)
    p.st(L.FRAME, 9)
    p.call(f"fwd{part}", lambda: FT.emit_forward(p, At(L.FRAME), L.FFT, part))


N_JOBS = 15                       # one a block; the hop's last block does none


def emit_job(p: Prog, L: Layout, k: int) -> None:
    _jobs(L)[k](p)


# ================================================================================ the voice
VT_NAMES = ("SPD", "VG", "PG", "GG", "GINC", "GLEN", "SQ", "LEV")
WIN_WORDS = LV.WIN_LEN + 1


def voice_tables_words() -> list[int]:
    """The voice's control tables (128 floats each, VT_NAMES' order), then the seven grain
    windows (129 floats each)."""
    out = []
    for n in VT_NAMES:
        out += [struct.unpack("<I", struct.pack("<f", float(x)))[0] for x in LV.TABLES[n]]
    for w in LV.TABLES["WIN"]:
        out += [struct.unpack("<I", struct.pack("<f", float(x)))[0] for x in w]
    return out


KNOBS = LV.CONTROLS                       # TUNE SPD BLND SAMP STRT SIZE DENS OVLP SPRY PRND WIN LEV
LANE_WORDS = 4                            # a lane's own words after its P and ring: POS, PITCH, R, ARMED
STATE_MAGIC = 0x534D5232                  # 'SMR2' (RIFT v0.26: the stretch's words; SMR1 before)


class VLayout:
    """The voice's fixed scratch (one voice at a time), byte addresses.

    Inputs, written by the sampler's glue before the block:
    - KN: the twelve knobs, 0..127 (KNOBS' order);
    - TR, RATE (floats);
    - TRIG, SIZE, BASE, FMT, CLOCK, LANE (-1, 0 or 1);
    - VSTATE: the voice's state in DDR.

    Then the voice's state as copied in (PI, PF, then the grains' state words), the
    grains' and the vocoder's layouts, the outputs and the tables."""

    def __init__(self, base: int, tables: int, vtables: int, lanes: tuple, fft=None):
        a = base
        names = [f"KN{k}" for k in range(len(KNOBS))] + ["TR", "RATE", "TRIG", "SIZE", "BASE", "FMT",
                                                  "CLOCK", "LANE", "VSTATE", "LSTART", "LEND",
                                                  "LSIZE", "SI", "SF", "VG", "PG", "GG", "JOB",
                                                  "LW2", "LWD", "LST", "TMP", "CNT2",
                                                  "TI", "TF", "HEADS", "HVA",   # RIFT v0.24: PLAY's heads
                                                  "KX", "KPOS", "KKEY", "KKP", "KPI0", "KT"]   # RIFT v0.26: the stretch's scratch
        for k, n in enumerate(names):
            setattr(self, n, a + 4 * k)
        a += 4 * len(names)
        a = (a + 63) & ~63
        self.MAGIC, self.PI, self.PF = a, a + 4, a + 8
        # RIFT v0.24: PLAY's two heads and their cycle, in the state's free words before the grains
        self.QA, self.QAF, self.QB, self.QBF, self.PH = a + 12, a + 16, a + 20, a + 24, a + 28
        # RIFT v0.26: the keyframe stretch's state (live.Voice.kf_reset), the grains moved on to make room
        for k, n in enumerate(("KP", "KPF", "KO", "KOF", "KW", "KFI", "KFD", "KC", "KS", "RKX", "RKN",
                               "PXL", "PDS", "PVK", "PLI", "RXL", "RDS", "RVK", "RLI")):
            setattr(self, n, a + 32 + 4 * k)
        self.G = GLayout(a + 128)
        # the state copied in and out: MAGIC .. the grains' end (the grains' inputs ride along)
        self.STATE_WORDS = (self.G.G + 32 * LV.GRAINS - self.MAGIC) // 4
        a = self.G.end
        self.L = Layout(a, tables, lane=(self.LW2, self.LWD), fft=fft)   # FFT: an fft.Tabs (RIFT v0.16: the pairs apart)
        a = self.L.end
        self.VOUT = a; a += 128
        self.OUT = a; a += 128
        self.end = a
        self.VT = vtables
        self.lanes = lanes                # ((L2 base, DDR base), (L2 base, DDR base))

    def vt(self, name: str) -> int:
        return self.VT + 512 * VT_NAMES.index(name)

    def win(self, k: int) -> int:
        return self.VT + 512 * len(VT_NAMES) + 4 * WIN_WORDS * k


def _tab(p: Prog, d: int, V: VLayout, name: str, knob: int) -> None:
    """Fd = table NAME at the knob KNOB's value (uses R12, I3)."""
    p.ld(d, V.KN0 + 4 * KNOBS.index(knob) if isinstance(knob, str) else knob)
    p.lsh(d, d, 2)
    p.iconst(12, V.vt(name))
    p.iop(d, 12, "+", d)
    p.seti(3, d)
    p.ldi(d, 0, 3)


def _copy(p: Prog, src_word: int, dst: int, n: int, out: bool) -> None:
    """n words between the DDR address in SRC_WORD and the fixed DST (OUT: fixed -> DDR)."""
    p.ld(9, src_word)
    p.seti(1, 9)
    p.iconst(9, dst)
    p.seti(2, 9)

    def body():
        if out:
            p.ldpost(0, 2)
            p.stpost(1, 0)
        else:
            p.ldpost(0, 1)
            p.stpost(2, 0)
    p.loop_r(15, n, body)


def _recip(p: Prog, d: int, x: int) -> None:
    """Fd = live.recip(Fx): the seed 0x7ef311c7 - bits, three Newton steps (uses R12, R13)."""
    p.iconst(12, 0x7EF311C7)
    p.iop(d, 12, "-", x)
    for _ in range(3):
        p.fop(12, x, "*", d)
        p.fconst(13, 2.0)
        p.fop(12, 13, "-", 12)
        p.fop(d, d, "*", 12)


def _kf_reset(p: Prog, V: VLayout, pos: int | None) -> None:
    """RIFT v0.26: live.Voice.kf_reset at PI (POS None) or 0."""
    if pos is None:
        p.ld(0, V.PI)
    else:
        p.iconst(0, pos)
    for w in ("KP", "KO"):
        p.st(getattr(V, w), 0)
    p.iconst(0, 0)
    for w in ("KPF", "KOF", "KW", "KFI", "KFD", "KC", "KS", "PXL", "PDS", "PVK", "RXL", "RDS", "RVK"):
        p.st(getattr(V, w), 0)
    p.iconst(0, -1)
    for w in ("RKX", "RKN", "PLI", "RLI"):
        p.st(getattr(V, w), 0)


def _kf_detect(p: Prog, V: VLayout, XL: int, DS: int, VK: int, LI: int) -> None:
    """RIFT v0.26: live.Voice.detect at KPOS (not LI), its sample at KX: KKEY (+1, -1, 0), KKP."""
    p.iconst(0, 0)
    p.st(V.KKEY, 0)
    p.ld(1, V.KX)
    p.ld(2, XL)
    p.fop(3, 1, "-", 2)                              # df

    def flat():
        p.ld(0, V.KPOS)
        p.st(LI, 0)

    def moved():
        p.iconst(4, 1)
        p.ifz(3, "LT", lambda: p.iconst(4, -1), kind="f")   # sg
        p.ld(5, DS)

        def turned():
            p.ld(1, XL)
            p.ld(2, VK)
            p.fop(3, 1, "-", 2)

            def key():
                p.ld(5, DS)
                p.st(V.KKEY, 5)
                p.ld(1, XL)
                p.st(VK, 1)
                p.ld(0, LI)
                p.st(V.KKP, 0)
            p.fconst(6, LV.KF_EPS)
            p.if_(3, "GE", 6, key, lambda: (p.fconst(6, -LV.KF_EPS), p.if_(3, "LE", 6, key)))
        p.ifz(5, "NE", lambda: p.if_(4, "NE", 5, turned, kind="i"))
        p.ld(1, V.KX)
        p.st(XL, 1)
        p.st(DS, 4)
        p.ld(0, V.KPOS)
        p.st(LI, 0)
    p.ifz(3, "EQ", flat, moved, kind="f")


def _kf_splice(p: Prog, V: VLayout, frac: int) -> None:
    """RIFT v0.26: live.Voice.splice: the play head to R10 (unwrapped), its fraction the word FRAC."""
    p.ld(1, frac)
    p.st(V.KT, 1)
    p.ld(0, V.KP)
    p.st(V.KO, 0)
    p.ld(0, V.KPF)
    p.st(V.KOF, 0)
    p.ld(13, V.SIZE)
    wrap(p, 10, 13)
    p.st(V.KP, 10)
    p.st(V.PLI, 10)
    p.ld(1, V.KT)
    p.st(V.KPF, 1)
    p.ld(8, V.KS)
    p.lsh(8, 8, -1)
    p.iconst(12, LV.KF_FADE_MIN)
    p.iop(8, 8, "MAX", 12)
    p.iconst(12, LV.KF_FADE)
    p.iop(8, 8, "MIN", 12)
    p.iconst(12, 0)
    p.float_(1, 8, 12)
    _recip(p, 2, 1)
    p.st(V.KFI, 2)
    p.iconst(0, 0)
    for w in ("KW", "KC", "KS"):
        p.st(getattr(V, w), 0)
    p.iconst(0, 1)
    p.st(V.KFD, 0)


def emit_voice(p: Prog, V: VLayout) -> None:
    """live.Voice.block for one voice: 32 samples into V.OUT."""
    G, L = V.G, V.L
    p.comment("SMEAR voice: its state in")
    _copy(p, V.VSTATE, V.MAGIC, V.STATE_WORDS, False)
    p.ld(0, V.MAGIC)
    p.iconst(1, STATE_MAGIC)

    def fresh():                                   # DDR is not cleared at power-on: the first use clears it
        p.iconst(0, 0)
        p.iconst(9, V.MAGIC)
        p.seti(1, 9)
        p.loop_r(15, V.STATE_WORDS, lambda: p.stpost(1, 0))
        p.iconst(1, STATE_MAGIC)
        p.st(V.MAGIC, 1)
        if LV.KF_ON:
            _kf_reset(p, V, 0)                       # RIFT v0.26: as live.Voice() (no keyframes: -1)
    p.if_(0, "NE", 1, fresh, kind="i")
    # -- the loop
    p.ld(13, V.SIZE)
    p.iconst(12, 0)
    p.float_(1, 13, 12)                              # size
    p.ld(0, V.KN0 + 4 * KNOBS.index("STRT"))
    p.float_(0, 0, 12)
    p.fconst(2, 1 / 128)
    p.fop(0, 0, "*", 2)
    p.fop(0, 0, "*", 1)
    p.trunc(4, 0)                                    # lstart
    p.st(V.LSTART, 4)
    p.ipass(14, 4)
    p.iop(5, 13, "-", 14)
    p.iconst(12, 0)
    p.float_(1, 5, 12)
    _tab(p, 0, V, "SQ", "SIZE")
    p.fop(0, 0, "*", 1)
    p.trunc(5, 0)
    p.iconst(12, LV.MIN_LOOP)
    p.iop(5, 5, "MAX", 12)                           # lsize
    p.st(V.LSIZE, 5)
    p.iop(5, 14, "+", 5)
    p.st(V.LEND, 5)
    # -- the speed
    _tab(p, 0, V, "SPD", "SPD")
    p.ld(1, V.RATE)                                  # RIFT v0.24: the read point at SPD x the rate alone (v0.22: x tr)
    p.fop(0, 0, "*", 1)
    p.trunc(2, 0)
    p.iconst(12, 0)
    p.float_(3, 2, 12)
    p.if_(3, "GT", 0, lambda: (p.iconst(12, 1), p.iop(2, 2, "-", 12), p.iconst(12, 0),
                               p.float_(3, 2, 12)))
    p.st(V.SI, 2)
    p.fop(0, 0, "-", 3)
    p.st(V.SF, 0)
    # RIFT v0.24: the heads' step, tr split as the speed is; HEADS = 1 unless they would step as the read point
    p.ld(0, V.TR)
    p.trunc(2, 0)
    p.iconst(12, 0)
    p.float_(3, 2, 12)
    p.if_(3, "GT", 0, lambda: (p.iconst(12, 1), p.iop(2, 2, "-", 12), p.iconst(12, 0),
                               p.float_(3, 2, 12)))
    p.st(V.TI, 2)
    p.fop(0, 0, "-", 3)
    p.st(V.TF, 0)
    p.iconst(4, 1)
    p.ld(5, V.SI)
    p.ld(1, V.SF)

    def same_i():
        p.if_(0, "EQ", 1, lambda: p.iconst(4, 0))
    p.if_(2, "EQ", 5, same_i, kind="i")
    p.st(V.HEADS, 4)
    for n in ("VG", "PG", "GG"):
        _tab(p, 0, V, n, "BLND")
        p.st(getattr(V, n), 0)

    def frozen():                                    # RIFT v0.22 FREEZE (live.Voice.block): the read point held, PLAY's share to GRN
        p.iconst(0, 0)
        p.st(V.SI, 0)
        p.st(V.SF, 0)
        p.ld(0, V.GG)
        p.ld(1, V.PG)
        p.fop(0, 0, "+", 1)
        p.st(V.GG, 0)
        p.iconst(0, 0)
        p.st(V.PG, 0)
    p.ld(0, V.KN0 + 4 * KNOBS.index("FRZ"))
    p.iconst(12, LV.FRZ_ON)
    p.if_(0, "GE", 12, frozen, kind="i")

    # -- a trig
    def trig():
        p.ld(0, V.LSTART)
        p.st(V.PI, 0)
        p.st(V.QA, 0)                                # RIFT v0.24: the heads at the read point, their cycle at 0
        p.st(V.QB, 0)
        p.iconst(0, 0)
        p.st(V.PF, 0)
        p.st(V.QAF, 0)
        p.st(V.QBF, 0)
        p.st(V.PH, 0)
        if LV.KF_ON:
            _kf_reset(p, V, None)                    # RIFT v0.26: the stretch at the read point

        def clear_lane():
            _lane_bases(p, V)
            p.iconst(0, 0)
            at_reg(p, 9, L.P)
            p.seti(1, 9)
            p.loop_r(15, N + 2 + N + LANE_WORDS, lambda: p.stpost(1, 0))   # P, the ring, POS PITCH R ARMED
        p.ld(0, V.LANE)
        p.ifz(0, "GE", clear_lane)
    p.ld(0, V.TRIG)
    p.ifz(0, "NE", trig)

    # -- y = 0
    p.iconst(0, 0)
    p.iconst(9, V.OUT)
    p.seti(1, 9)
    p.loop_r(15, 32, lambda: p.stpost(1, 0))

    # -- VOC
    def voc():
        _lane_bases(p, V)
        lst = L.RING + 4 * N                         # the lane's words: POS PITCH R ARMED
        # the job: (CLOCK + 8 LANE) & 15
        p.ld(9, V.CLOCK)
        p.ld(0, V.LANE)
        p.lsh(0, 0, 3)
        p.iop(9, 9, "+", 0)
        p.iconst(12, 15)
        p.iop(9, 9, "AND", 12)
        p.st(V.JOB, 9)
        # the ring's 32 samples out (cleared behind), R moving on
        ldw(p, 13, lst + 8)                          # R
        at_reg(p, 14, L.RING)
        p.iconst(9, V.VOUT)
        p.seti(5, 9)

        def ring1():
            p.lsh(3, 13, 2)
            p.iop(3, 14, "+", 3)
            p.seti(0, 3)
            p.ldi(1, 0, 0)
            p.stpost(5, 1)
            p.iconst(1, 0)
            p.sti(0, 0, 1)
            p.iconst(12, 1)
            p.iop(13, 13, "+", 12)
            p.iconst(12, N - 1)
            p.iop(13, 13, "AND", 12)
        p.loop_r(15, 32, ring1)
        p.ipass(10, 13)
        stw(p, lst + 8, 10)
        # job 0: latch the read point (spos) and the pitch, and arm
        p.ld(9, V.JOB)

        def latch():
            p.ld(9, V.PI)
            p.iconst(12, -LV.HOP)
            p.iop(9, 9, "AND", 12)                   # HOP x floor(pi / HOP)
            p.iconst(12, 1)
            p.iop(9, 9, "-", 12)
            p.ld(13, V.SIZE)
            wrap(p, 9, 13)
            p.iconst(12, 1)
            p.iop(9, 12, "+", 9)                     # (spos - 1) % size + 1
            stw(p, lst, 9)
            p.ld(0, V.TR)
            stw(p, lst + 4, 0)
            p.iconst(0, 1)
            stw(p, lst + 12, 0)
        p.ifz(9, "EQ", latch)
        # the hop's job, once armed
        ldw(p, 0, lst + 12)

        def jobs():
            ldw(p, 0, lst)
            p.st(L.POS, 0)
            ldw(p, 0, lst + 4)
            p.st(L.PITCH, 0)
            ldw(p, 0, lst + 8)
            p.st(L.R, 0)
            for w in ("SIZE", "BASE", "FMT"):
                p.ld(0, getattr(V, w))
                p.st(getattr(L, w), 0)
            p.ld(9, V.JOB)
            for k in range(N_JOBS):
                p.iconst(12, k)
                p.if_(9, "EQ", 12, lambda k=k: (emit_job(p, L, k), p.ld(9, V.JOB)), kind="i")
        p.ifz(0, "NE", jobs)
        # y = y + vg voc
        p.ld(2, V.VG)
        p.iconst(9, V.VOUT)
        p.seti(4, 9)
        p.iconst(9, V.OUT)
        p.seti(5, 9)

        def mix():
            p.ldpost(0, 4)
            p.fop(0, 2, "*", 0)
            p.ldi(1, 0, 5)
            p.fop(1, 1, "+", 0)
            p.stpost(5, 1)
        p.loop_r(15, 32, mix)
    p.ld(0, V.VG)
    p.iconst(1, 0)

    def vg_on():
        p.ld(0, V.LANE)
        p.ifz(0, "GE", voc)
    if LV.VOC_ON:          # RIFT v0.20: VOC off (live.VOC_ON): its code left out, the DSP's room freed (VG is 0)
        p.if_(0, "GT", 1, vg_on)

    # -- GRN
    def grn():
        p.ld(0, V.PI)
        p.st(G.READ, 0)
        p.ld(0, V.TR)
        p.st(G.PITCH, 0)
        _tab(p, 0, V, "GINC", "DENS")
        p.st(G.GINC, 0)
        _tab(p, 0, V, "SQ", "OVLP")
        _tab(p, 1, V, "GLEN", "DENS")
        p.fop(0, 0, "*", 1)
        p.fconst(1, 1.0)
        p.fop(0, 0, "+", 1)
        p.fconst(1, 8000.0)
        p.fop(0, 0, "MIN", 1)
        p.fconst(1, 48.0)
        p.fop(0, 0, "*", 1)
        _recip(p, 2, 0)
        p.st(G.ENVINC, 2)
        _tab(p, 0, V, "SQ", "SPRY")
        p.st(G.SPRAY, 0)
        _tab(p, 0, V, "SQ", "PRND")
        p.st(G.PRAND, 0)
        # the window: min(WIN x 7 >> 7, 6)
        p.ld(0, V.KN0 + 4 * KNOBS.index("WIN"))
        p.lsh(1, 0, 3)
        p.iop(0, 1, "-", 0)                         # x 7
        p.lsh(0, 0, -7)
        p.iconst(12, 6)
        p.iop(0, 0, "MIN", 12)
        p.iconst(12, 4 * WIN_WORDS)
        p.mul_ssi(0, 0, 12)
        p.iconst(12, V.win(0))
        p.iop(0, 12, "+", 0)
        p.st(G.WINP, 0)
        for w in ("SIZE", "BASE", "FMT"):
            p.ld(0, getattr(V, w))
            p.st(getattr(G, w), 0)
        emit_grn(p, G)
        p.ld(2, V.GG)
        p.iconst(9, G.OUT)
        p.seti(4, 9)
        p.iconst(9, V.OUT)
        p.seti(5, 9)

        def mix():
            p.ldpost(0, 4)
            p.fop(0, 2, "*", 0)
            p.ldi(1, 0, 5)
            p.fop(1, 1, "+", 0)
            p.stpost(5, 1)
        p.loop_r(15, 32, mix)
    p.ld(0, V.GG)
    p.iconst(1, 0)
    p.if_(0, "GT", 1, grn)

    # -- PLAY, and the read point moves on
    p.comment("SMEAR PLAY and the read point")
    p.iconst(9, V.OUT)
    p.seti(5, 9)

    def sample():
        p.ld(0, V.PG)
        p.iconst(1, 0)

        def at(qi, qf):                              # F7 = the buffer at (qi, qf), live.Voice.block's at()
            p.ld(13, V.SIZE)
            p.ld(14, V.BASE)
            fetch(p, 6, 10, 14, V.FMT, 9, 0)
            p.iconst(12, 1)
            p.iop(3, 12, "+", 10)
            p.if_(3, "GE", 13, lambda: p.iconst(3, 0), kind="i")
            fetch(p, 7, 3, 14, V.FMT, 9, 0)
            p.fop(7, 7, "-", 6)
            p.ld(5, qf)
            p.fop(7, 5, "*", 7)
            p.fop(7, 6, "+", 7)

        def plain():
            p.ld(10, V.PI)
            p.ld(13, V.SIZE)
            wrap(p, 10, 13)
            at(V.PI, V.PF)
            p.ld(0, V.PG)
            p.fop(7, 0, "*", 7)
            p.ldi(1, 0, 5)
            p.fop(1, 1, "+", 7)
            p.sti(0, 5, 1)

        def step(qi, qf):                            # live's step(): (qi, qf) += (TI, TF), wrapped at the size
            p.ld(0, qf)
            p.ld(1, V.TF)
            p.fop(0, 0, "+", 1)
            p.ld(10, qi)
            p.ld(2, V.TI)
            p.iop(10, 10, "+", 2)
            p.fconst(1, 1.0)
            p.if_(0, "GE", 1, lambda: (p.fop(0, 0, "-", 1), p.iconst(12, 1), p.iop(10, 10, "+", 12)))
            p.st(qf, 0)
            p.ld(13, V.SIZE)
            p.if_(10, "GE", 13, lambda: p.iop(10, 10, "-", 13), kind="i")
            p.st(qi, 10)

        def heads():
            p.ld(10, V.QA)
            at(V.QA, V.QAF)
            p.st(V.HVA, 7)                           # va
            p.ld(10, V.QB)
            at(V.QB, V.QBF)                          # F7 = vb
            p.ld(0, V.PH)
            p.fop(2, 0, "+", 0)                      # ph + ph
            p.fconst(1, 0.5)
            p.if_(0, "LT", 1, lambda: None, lambda: (p.fconst(3, 2.0), p.fop(2, 3, "-", 2)))   # wa
            p.fconst(3, 1.0)
            p.fop(3, 3, "-", 2)                      # wb = 1 - wa
            p.ld(4, V.HVA)
            p.fop(4, 2, "*", 4)                      # wa va
            p.fop(7, 3, "*", 7)                      # wb vb
            p.fop(7, 4, "+", 7)
            p.ld(0, V.PG)
            p.fop(7, 0, "*", 7)
            p.ldi(1, 0, 5)
            p.fop(1, 1, "+", 7)
            p.sti(0, 5, 1)
            step(V.QA, V.QAF)
            step(V.QB, V.QBF)

        def play():
            p.ld(0, V.HEADS)
            p.ifz(0, "NE", heads, plain)

        def kf():                                    # RIFT v0.26: VOC's share through the keyframe stretch (live.Voice.block)
            p.ld(10, V.PI)
            p.ld(13, V.SIZE)
            wrap(p, 10, 13)
            p.st(V.KPI0, 10)
            p.ld(11, V.RLI)

            def rdet():
                p.ld(14, V.BASE)
                fetch(p, 1, 10, 14, V.FMT, 9, 0)
                p.st(V.KX, 1)
                p.st(V.KPOS, 10)
                _kf_detect(p, V, V.RXL, V.RDS, V.RVK, V.RLI)
                p.ld(0, V.KKEY)

                def found():
                    p.ld(1, V.KKP)
                    p.ifz(0, "GT", lambda: p.st(V.RKX, 1), lambda: p.st(V.RKN, 1))
                    p.ld(8, V.KC)
                    p.iconst(12, 1)
                    p.iop(8, 8, "-", 12)
                    p.st(V.KC, 8)
                p.ifz(0, "NE", found)
            p.if_(10, "NE", 11, rdet, kind="i")
            p.ld(10, V.KP)
            at(V.KP, V.KPF)                          # F7 = v, F6 = x0
            p.st(V.KX, 6)
            p.ld(0, V.KFD)

            def fading():
                p.st(V.HVA, 7)
                p.ld(10, V.KO)
                at(V.KO, V.KOF)                      # F7 = vo
                p.ld(4, V.HVA)
                p.fop(4, 4, "-", 7)
                p.ld(5, V.KW)
                p.fop(4, 5, "*", 4)
                p.fop(7, 7, "+", 4)
            p.ifz(0, "NE", fading)
            p.ld(0, V.VG)
            p.fop(7, 0, "*", 7)
            p.ldi(1, 0, 5)
            p.fop(1, 1, "+", 7)
            p.sti(0, 5, 1)
            p.ld(10, V.KP)
            p.ld(11, V.PLI)

            def pdet():
                p.st(V.KPOS, 10)
                _kf_detect(p, V, V.PXL, V.PDS, V.PVK, V.PLI)
                p.ld(0, V.KKEY)

                def found():
                    p.ld(8, V.KC)
                    p.iconst(12, 1)
                    p.iop(8, 8, "+", 12)
                    p.st(V.KC, 8)
                    p.ld(11, V.RKX)
                    p.ifz(0, "LT", lambda: p.ld(11, V.RKN))

                    def free():
                        def rk_ok():
                            p.iconst(3, 0)
                            p.ld(8, V.KC)
                            p.iconst(12, LV.KF_K)
                            p.if_(8, "GT", 12, lambda: p.iconst(3, 1), kind="i")
                            p.iconst(12, -LV.KF_K)
                            p.if_(8, "LT", 12, lambda: p.iconst(3, 1), kind="i")
                            p.ld(8, V.KS)
                            p.iconst(12, LV.KF_GRAIN)
                            p.if_(8, "GE", 12, lambda: p.iconst(3, 1), kind="i")

                            def go():
                                p.ld(8, V.KP)
                                p.ld(9, V.KKP)
                                p.iop(9, 8, "-", 9)
                                p.iop(10, 11, "+", 9)       # rk + (kp - kkp)
                                _kf_splice(p, V, V.KPF)
                            p.ifz(3, "NE", go)
                        p.ifz(11, "GE", rk_ok)
                    p.ld(2, V.KFD)
                    p.ifz(2, "EQ", free)
                p.ifz(0, "NE", found)
            p.if_(10, "NE", 11, pdet, kind="i")
            p.ld(0, V.KFD)

            def forced():
                p.ld(8, V.KS)
                p.iconst(12, 2 * LV.KF_GRAIN)
                p.if_(8, "GE", 12, lambda: (p.ld(10, V.KPI0), _kf_splice(p, V, V.PF)), kind="i")
            p.ifz(0, "EQ", forced)
            p.ld(8, V.KS)
            p.iconst(12, 1)
            p.iop(8, 8, "+", 12)
            p.st(V.KS, 8)
            p.ld(0, V.KFD)

            def adv():
                p.ld(1, V.KW)
                p.ld(2, V.KFI)
                p.fop(1, 1, "+", 2)
                p.st(V.KW, 1)
                step(V.KO, V.KOF)
                p.ld(1, V.KW)
                p.fconst(2, 1.0)
                p.if_(1, "GE", 2, lambda: (p.iconst(0, 0), p.st(V.KFD, 0)))
            p.ifz(0, "NE", adv)
            step(V.KP, V.KPF)
        if LV.KF_ON:
            p.ld(0, V.VG)
            p.iconst(1, 0)
            p.if_(0, "GT", 1, kf)
            p.ld(0, V.PG)
            p.iconst(1, 0)
        p.if_(0, "GT", 1, play)
        # pf += sf; pi += si; carry; wrap into [lstart, lend)
        p.ld(0, V.PF)
        p.ld(1, V.SF)
        p.fop(0, 0, "+", 1)
        p.ld(10, V.PI)
        p.ld(2, V.SI)
        p.iop(10, 10, "+", 2)
        p.fconst(1, 1.0)
        p.if_(0, "GE", 1, lambda: (p.fop(0, 0, "-", 1), p.iconst(12, 1), p.iop(10, 10, "+", 12)))
        p.st(V.PF, 0)
        p.ld(11, V.LEND)
        p.ld(13, V.LSIZE)
        p.ld(14, V.LSTART)
        _wrap_loop(p, 10, 11, 13, 14)
        p.st(V.PI, 10)
        # RIFT v0.24: the heads' cycle (live.Voice.block): each restarts at the read point where its
        # triangle is 0; not reading through them, they follow the read point (R10, F0: pi, pf)
        p.st(V.TMP, 0)

        def cycle():
            p.ld(1, V.PH)
            p.fconst(2, LV.HEAD_INC)
            p.fop(2, 1, "+", 2)                      # ph
            p.fconst(3, 1.0)

            def wrapped():
                p.fop(2, 2, "-", 3)
                p.st(V.QA, 10)
                p.ld(0, V.TMP)
                p.st(V.QAF, 0)

            def half():
                p.fconst(3, 0.5)

                def crossed():
                    p.st(V.QB, 10)
                    p.ld(0, V.TMP)
                    p.st(V.QBF, 0)
                p.if_(1, "LT", 3, lambda: p.if_(2, "GE", 3, crossed))
            p.if_(2, "GE", 3, wrapped, half)
            p.st(V.PH, 2)

        def follow():
            p.st(V.QA, 10)
            p.st(V.QB, 10)
            p.ld(0, V.TMP)
            p.st(V.QAF, 0)
            p.st(V.QBF, 0)

        def by_heads():
            p.ld(0, V.HEADS)
            p.ifz(0, "NE", cycle, follow)
        p.ld(0, V.PG)
        p.iconst(1, 0)
        p.if_(0, "GT", 1, by_heads, follow)
        if LV.KF_ON:                                 # RIFT v0.26: no VOC share: the stretch follows the read point (R10, TMP)

            def kf_follow():
                p.st(V.KP, 10)
                p.ld(0, V.TMP)
                p.st(V.KPF, 0)
                p.iconst(0, 0)
                for w in ("KFD", "KC", "KS"):
                    p.st(getattr(V, w), 0)
                p.iconst(0, -1)
                p.st(V.PLI, 0)
            p.ld(0, V.VG)
            p.iconst(1, 0)
            p.if_(0, "GT", 1, lambda: None, kf_follow)
        p.iconst(9, 1)
        p.ldi(0, 0, 5)
        p.stpost(5, 0)                               # on to the next sample
    p.loop(V.CNT2, 32, sample)
    # -- x LEV
    _tab(p, 2, V, "LEV", "LEV")
    p.iconst(9, V.OUT)
    p.seti(5, 9)

    def lev():
        p.ldi(0, 0, 5)
        p.fop(0, 0, "*", 2)
        p.stpost(5, 0)
    p.loop_r(15, 32, lev)
    p.comment("SMEAR voice: its state out")
    _copy(p, V.VSTATE, V.MAGIC, V.STATE_WORDS, True)


def _lane_bases(p: Prog, V: VLayout) -> None:
    """LW2, LWD = the lane's L2 and DDR bases (LANE 0 or 1)."""
    p.ld(0, V.LANE)
    (a0, d0), (a1, d1) = V.lanes
    p.iconst(1, a0)
    p.iconst(2, d0)
    p.ifz(0, "NE", lambda: (p.iconst(1, a1), p.iconst(2, d1)))
    p.st(V.LW2, 1)
    p.st(V.LWD, 2)


def _wrap_loop(p: Prog, r: int, lend: int, lsize: int, lstart: int) -> None:
    """while r >= lend: r -= lsize; while r < lstart: r += lsize (all R8..R15)."""
    if p.run:
        while True:
            p.e("COMP")
            if p._cmp(r, lend, "i") >= 0:
                p.iop(r, r, "-", lsize)
                continue
            p.e("COMP")
            if p._cmp(r, lstart, "i") < 0:
                p.iop(r, r, "+", lsize)
                continue
            break
        return
    top, low, done = p.label("lw"), p.label("lwlo"), p.label("lwok")
    p.place(top)
    p.e(f"COMP(R{r}, R{lend});")
    p.jump("LT", low)
    p.iop(r, r, "-", lsize)
    p.jump("", top)
    p.place(low)
    p.e(f"COMP(R{r}, R{lstart});")
    p.jump("GE", done)
    p.iop(r, r, "+", lsize)
    p.jump("", low)
    p.place(done)


def write_ddr_json() -> None:
    """dnfw.smear.ddr's file: the three tables dsp.link_tables sends (the build reads it, numpy-free)"""
    import json
    from . import ddr
    from . import stage as SG
    tabs = {"vtables": voice_tables_words(), "qsin": SG.qsin_words(), "pairs": SG.pairs_words()}
    data = {"note": "generated by scripts/gen_smear_asm.py from dnfw.smear; do not edit"}
    data.update({k: [f"{w & 0xFFFFFFFF:08x}" for w in v] for k, v in tabs.items()})
    ddr.DDR_JSON.write_text(json.dumps(data) + "\n", encoding="utf-8", newline="\n")
