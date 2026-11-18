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

N = LV.FFT_N
MAGIC = 0x5F3759DF


class Layout:
    """Byte addresses. Params: POS, PITCH (float), SIZE (int), BASE (the buffer's first
    sample, float32), R (the ring's read point, int)."""

    def __init__(self, base: int, tables: int):
        a = base
        self.POS, self.PITCH, self.SIZE, self.BASE, self.R, self.CNT = (a + 4 * k for k in range(6))
        a += 64
        self.WF = a; a += 4 * N
        self.WB = a; a += 4 * N
        self.D = a; a += 4 * (N + 2)
        self.P = a; a += 4 * (N + 2)
        self.RING = a; a += 4 * N
        self.end = a
        self.WIN = tables
        self.FFT = tables + 4 * N


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


# ---------------------------------------------------------------------------- the jobs
def emit_read(p: Prog, L: Layout, B: bool = False) -> None:
    """WF (WB): sample(pf [- hp]) x WIN for i = 0..N-1, as live.read_frames."""
    p.comment(f"SMEAR read {'B' if B else 'F'}")
    p.ld(10, L.POS)
    p.ld(9, L.PITCH)
    p.ld(13, L.SIZE)
    p.ld(14, L.BASE)
    p.fconst(8, float(LV.HOP))
    p.fop(8, 8, "*", 9)                          # hp
    p.iconst(11, 0)
    p.float_(11, 11, 11)                         # fi = 0.0 (FLOAT 0 BY 0)
    p.iconst(0, L.WIN)
    p.seti(4, 0)
    p.iconst(0, L.WB if B else L.WF)
    p.seti(5, 0)

    def body():
        p.fop(0, 9, "*", 11)
        p.fop(0, 10, "+", 0)                     # pf
        p.trunc(2, 0)
        p.iconst(3, 0)
        p.float_(4, 2, 3)
        p.fop(5, 0, "-", 4)                      # frac
        if B:
            p.fop(1, 0, "-", 8)
            p.trunc(2, 1)
        wrap(p, 2, 13)
        p.lsh(3, 2, 2)
        p.iop(3, 14, "+", 3)
        p.seti(0, 3)
        p.ldi(6, 0, 0)                           # s0
        p.iconst(12, 1)
        p.iop(3, 12, "+", 2)
        p.fpass(7, 6)                            # s1 = s0 at the end ...
        p.if_(3, "LT", 13, lambda: p.ldi(7, 1, 0), kind="i")   # ... else the next sample
        p.fop(7, 7, "-", 6)
        p.fop(7, 5, "*", 7)
        p.fop(7, 6, "+", 7)                      # s0 + frac (s1 - s0)
        p.ldpost(6, 4)
        p.fop(7, 7, "*", 6)
        p.stpost(5, 7)
        p.fconst(6, 1.0)
        p.fop(11, 11, "+", 6)
    p.loop_r(15, N, body)


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
        p.ld(0, L.P + 4 * pw)
        p.ld(1, L.P + 4 * pw + 4)
        p.ld(2, L.WB + 4 * bw)
        p.iconst(3, 0)
        _bin1(p)
        p.st(L.D + 4 * dw, 4)
        p.st(L.D + 4 * dw + 4, 5)
    for i, a in ((1, L.P + 8), (2, L.WB + 8), (3, L.D + 8)):
        p.iconst(9, a)
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
    p.ld(0, L.WF)
    p.iconst(1, 0)
    _bin2(p)
    p.st(L.WF, 2)
    p.st(L.P, 2)
    p.iconst(3, 0)
    p.st(L.P + 4, 3)
    p.ld(4, L.D + 4 * (N - 2))
    p.ld(6, L.D + 4 * N)
    p.fop(4, 4, "+", 6)                          # lrN = d1023r + d1024r
    p.iconst(5, 0)
    p.ld(0, L.WF + 4)
    p.iconst(1, 0)
    _bin2(p)
    p.st(L.WF + 4, 2)
    p.st(L.P + 4 * N, 2)
    p.iconst(3, 0)
    p.st(L.P + 4 * N + 4, 3)
    for i, a in ((0, L.WF + 8), (1, L.P + 8), (3, L.D)):
        p.iconst(9, a)
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
    p.iconst(14, L.RING)
    p.iconst(0, L.WIN)
    p.seti(4, 0)
    p.iconst(0, L.WF)
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
