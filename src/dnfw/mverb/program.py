"""RIFT's master reverb on the SHARC (v0.21): `dnfw.mverb.live.Verb` in FASCIA's expression compiler
with ORGAN's leaves, as PLATEAU's program is (its line and allpass routines are PLATEAU's own).

**Where it runs.** In the stock FX function (sw 0xb836ac), in place of the stock reverb's core: the
core's call at sw 0xb8370c (`CALL 0xb82d1a (DB)` and its two delay-slot pushes, 18 bytes) becomes
`JUMP wr_mv`; wr_mv saves the registers it uses, renders a block, puts them back and jumps on to
sw 0xb83715, past the call. The stock input stage (sends, the input HPF and LPF) has written the 32
mono samples it reads (IN_BUF); the stock mix stage (MIX VOL, routing) reads the 64 it writes
(OUT_L, OUT_R). Its controls are the frame's reverb words (FRAME + 2586 ..).

**Its state.** STATE (DDR): the magic, the lines' clearing counter, the write index, the LFO phase,
the two shelves, the tank's two ends; the lines from STATE + LINES_AT. A fresh instance (the magic
not there) clears its lines, CHUNK words a block, silent meanwhile.

**Its scratch.** FASCIA's arrays (L1): the FX function runs after FASCIA's walk, never during it.
"""
from __future__ import annotations

import pathlib
import re

import numpy as np

from ..fascia import program as FP_
from ..fascia.program import Kc, Mv, mn, mx, ab, BLOCK
from ..organ.program import exp2f, expf, sin_turns
from ..perc import program as PP
from ..perc.dsl import Mem
from ..plateau import program as PLP
from . import live as LV

F = np.float32
MAGIC = 0x4D564221                     # 'MVB!'
LINES_AT = 0x100
IN_BUF = 0x80058778                    # the stock input stage's 32 samples
OUT_L = 0x800587F8                     # the stock mix stage's 64: left, then right
OUT_R = 0x80058878
FRAME_PRE = 2586                       # the frame's FX slot (2554): slots 41.. (PRE, DEC, FREQ, GAIN)
SITE_SW = 0xB8370C                     # the stock core's call (and its delay slots: 18 bytes)
SITE_STOCK = None                      # read from the stock image at build time (dsp.py checks it)
RESUME_SW = 0xB83715                   # after the call
assert BLOCK == LV.SUB

# the state's words (DDR, at STATE)
STW = ("magic", "clr", "w", "ph", "shA", "shB", "endA", "endB")
ST = {n: 4 * i for i, n in enumerate(STW)}
SAVE = ("R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "R9", "R10", "R11", "R12", "R13", "R14",
        "R15", "I0", "I1", "I2", "I3", "I4", "I5", "I12", "M0", "M1", "M2", "M3", "M4", "ASTAT")


def k(x) -> Kc:
    return Kc(float(F(x)))


_SRC = pathlib.Path(__file__).read_text(encoding="utf-8")
WORDS = tuple(sorted(set(re.findall(r'\bc\("([A-Za-z_0-9]+)"\)', _SRC))
                     | {"wi", "dw", "lb", "lm", "apx", "apg", "z", "v", "apo", "di", "fr", "b0", "b1", "dd",
                        "cnt0", "cnt1", "pred", "ip", "op_l", "op_r", "yl", "yr", "na", "nb", "ma", "mb",
                        "hshA", "hshB", "hendA", "hendB"}))   # RIFT v0.27: the state words a sample reads, in L1 for the block


HOT = ("shA", "shB", "endA", "endB")
# RIFT v0.28 (the owner, 2026-11-26: "can we try optimizing the reverb ... less heavy while retaining sound and
# behavior"): the sample loop with its values in registers and the line addresses computed inline (MG.sample_fast),
# the same operations in the same order: bit for bit live.Verb, as v0.21..v0.27's loop (MG.sample, kept: False
# puts it back). The runner's rprof MVERB: 27,284 instructions and 43,263 cycles a block before.
FAST = True


class Layout:
    def __init__(self, fascia: FP_.Layout, state: int, save: int):
        self.fl = fascia
        self.state = state
        self.save = save                       # SAVE's words (L1)
        at = fascia.arrays
        self.C = {}
        for name in WORDS:
            self.C[name] = at
            at += 4
        self.A = {}
        self.words_end = at
        assert at <= fascia.scratch_end
        self.scratch, self.scratch_end, self.base5 = fascia.scratch, fascia.scratch_end, fascia.base5
        self.rets = fascia.rets

    def line(self, name: str) -> int:
        return self.state + LINES_AT + 4 * LV.OFF[name]

    def st(self, name: str) -> int:
        return self.state + ST[name]


class MG(PLP.PG):
    """PLATEAU's compiler (its line and allpass routines), the master reverb's block"""

    def s(self, name) -> Mv:                 # a state word (DDR)
        return Mv("a", self.L.st(name))

    def si(self, name) -> Mv:
        return Mv("a", self.L.st(name), isint=True)

    def _addr(self, line: str, ireg: int = 1) -> None:
        p = self.p
        p.iconst(12, LV.SIZE[line] - 1)
        p.iop(9, 9, "AND", 12)
        p.lsh(9, 9, 2)
        p.iconst(12, self.L.line(line))
        p.iop(9, 9, "+", 12)
        p.seti(ireg, 9)

    def setline(self, line: str, delay: int | None = None, dword: str | None = None) -> None:
        """lb, lm = the line's; dw = DELAY (a constant) or the int word DWORD"""
        p, C = self.p, self.L.C
        p.iconst(0, self.L.line(line))
        p.st(C["lb"], 0)
        p.iconst(0, LV.SIZE[line] - 1)
        p.st(C["lm"], 0)
        if dword is not None:
            p.ld(0, C[dword])
        else:
            p.iconst(0, delay)
        p.st(C["dw"], 0)

    def ap_c(self, line: str, x, d: int, g) -> None:
        """c('apo') = live.ap(line, x, d, g), d a constant"""
        c = self.c
        self.set(c("apx"), x)
        self.set(c("apg"), g)
        self.setline(line, d)
        self.rt("p_ap", self.ap_body)

    def rd_c(self, line: str, d: int, r: int = 0) -> None:
        """Fr = live.rd(line, d), d a constant"""
        p, C = self.p, self.L.C
        p.ld(9, C["wi"])
        p.iconst(10, d)
        p.iop(9, 9, "-", 10)
        self._addr(line)
        p.ldi(r, 0, 1)

    def wr_c(self, line: str, m: Mv) -> None:
        p, C = self.p, self.L.C
        p.ld(9, C["wi"])
        self._addr(line)
        self.ld(0, m)
        p.sti(0, 1, 0)

    # -- the routine -----------------------------------------------------------------------------
    def entry(self) -> None:
        p, L = self.p, self.L
        si = self.si

        def fresh():
            for n in STW:
                self.iset(si(n), 0)
            self.iset(si("magic"), MAGIC)
        self.icmp(si("magic"), "NE", MAGIC, fresh)
        self.icmp(si("clr"), "LT", LV.TOTAL, self.clearing, self.render)

    def out_zeros(self) -> None:
        p = self.p
        for base in (OUT_L, OUT_R):
            p.iconst(9, base)
            p.seti(4, 9)
            p.iconst(5, 0)
            p.loop_r(10, BLOCK, lambda: p.stpost(4, 5), one=11)

    def clearing(self) -> None:
        p, L = self.p, self.L
        self.ld(9, self.si("clr"))
        p.lsh(9, 9, 2)
        p.iconst(12, L.state + LINES_AT)
        p.iop(9, 9, "+", 12)
        p.seti(4, 9)
        p.iconst(5, 0)
        p.loop_r(10, LV.CHUNK, lambda: p.stpost(4, 5), one=11)
        self.ld(9, self.si("clr"))
        p.iconst(12, LV.CHUNK)
        p.iop(9, 9, "+", 12)
        self.st(self.si("clr"), 9)
        self.out_zeros()

    def word(self, dst: str, off: int) -> None:
        """c(dst) = the frame's 16-bit word at OFF, as a float"""
        p = self.p
        p.iconst(10, 0)
        PP.half(p, 4, off, 10)
        p.iconst(12, 0)
        p.float_(4, 4, 12)
        self.st(self.c(dst), 4)

    def render(self) -> None:
        p, C = self.p, self.L.C
        c, s = self.c, self.s
        # live.controls
        self.word("pw", FRAME_PRE)
        self.word("dw_", FRAME_PRE + 2)
        self.word("fw", FRAME_PRE + 4)
        self.word("gw", FRAME_PRE + 6)
        self.set(c("p"), c("pw") * k(LV.INV_T))
        self.set(c("d"), c("dw_") * k(LV.INV_T))
        self.set(c("fq"), c("fw") * k(LV.INV_T))
        self.set(c("g_sh"), c("gw") * k(LV.INV_T))
        self.set(c("u"), k(1.0) - c("d"))
        self.set(c("gdec"), mn(k(0.1) + k(LV.GDEC_SPAN) * (k(1.0) - c("u") * c("u")), k(LV.GDEC_MAX)))   # (v0.28: 0.87, 0.97)
        self.trunc_to("pred", c("p") * k(LV.PRED_K))
        self.set(c("gd2"), mn(mx(c("gdec") + k(0.15), k(0.25)), k(0.5)))
        self.set(c("c_sh"), PLP.onepole(k(500.0) * exp2f(c("fq") * k(5.25))))
        # the LFO
        self.set(c("ph0"), s("ph"))
        self.set(c("ph1"), c("ph0") + k(LV.LFO_INC))
        self.cmp(c("ph1"), "GE", k(1.0), lambda: self.set(c("ph1"), c("ph1") - k(1.0)))
        self.set(c("ma"), k(LV.EXC) * (k(1.0) + sin_turns(c("ph0"))))
        self.set(c("mb"), k(LV.EXC) * (k(1.0) + sin_turns(c("ph0") + k(0.25))))
        self.set(c("dma"), ((k(LV.EXC) * (k(1.0) + sin_turns(c("ph1")))) - c("ma")) * k(LV.INV_SUB))
        self.set(c("dmb"), ((k(LV.EXC) * (k(1.0) + sin_turns(c("ph1") + k(0.25)))) - c("mb")) * k(LV.INV_SUB))
        self.ld(0, self.si("w"))
        p.st(C["wi"], 0)
        for word, at in (("ip", IN_BUF), ("op_l", OUT_L), ("op_r", OUT_R)):
            p.iconst(0, at)
            p.st(C[word], 0)
        # RIFT v0.27 LEAN: the shelves' and the tank's end words in L1 for the block (copied in and out:
        # the same values, no DDR access a sample)
        for n in HOT:
            self.set(c("h" + n), s(n))
        p.loop(C["cnt0"], BLOCK, self.sample_fast if FAST else self.sample)
        for n in HOT:
            self.set(s(n), c("h" + n))
        self.set(s("ph"), c("ph1"))
        p.ld(0, C["wi"])
        self.st(self.si("w"), 0)

    def sample(self) -> None:
        p, C = self.p, self.L.C
        c, s = self.c, self.s
        self.ptr(4, "ip")
        self.set(c("x"), Mv("i", 4, 0))
        self.cmp(ab(c("x")), "LT", k(LV.IN_MAX), lambda: None, lambda: self.fz(c("x")))
        self.wr_c("pre", c("x"))

        def delayed():
            self.rd_to(0, "pre", "pred")
            self.st(c("x"), 0)
        self.icmp(self.ci("pred"), "GT", 0, delayed)
        for name, g in (("i0", LV.GI1), ("i1", LV.GI1), ("i2", LV.GI2), ("i3", LV.GI2)):
            self.ap_c(name, c("x"), LV.LEN[name], k(g))
            self.set(c("x"), c("apo"))
        for side, other, sh, end in (("a", "endB", "shA", "na"), ("b", "endA", "shB", "nb")):
            # live: apf(side_ap, x + gdec end_other, len + m), the d1 line, the shelf, ap2, the d2 line
            p.iconst(0, LV.LEN[side + "_ap"])
            p.iconst(12, 0)
            p.float_(0, 0, 12)
            self.ld(1, c("m" + side))
            p.fop(0, 0, "+", 1)
            self.st(c("dd"), 0)
            self.set(c("apx"), c("x") + c("gdec") * c("h" + other))
            self.set(c("apg"), k(LV.GD1))
            p.iconst(0, self.L.line(side + "_ap"))
            p.st(C["lb"], 0)
            p.iconst(0, LV.SIZE[side + "_ap"] - 1)
            p.st(C["lm"], 0)
            self.rt("p_apf", self.apf_body)
            self.wr_c(side + "_d1", c("apo"))
            self.rd_c(side + "_d1", LV.LEN[side + "_d1"])
            self.st(c("t1"), 0)
            hs = c("h" + sh)
            self.set(hs, hs + c("c_sh") * (c("t1") - hs))
            self.set(c("t1"), (hs + c("g_sh") * (c("t1") - hs)) * c("gdec"))
            self.ap_c(side + "_ap2", c("t1"), LV.LEN[side + "_ap2"], c("gd2"))
            self.wr_c(side + "_d2", c("apo"))
            self.rd_c(side + "_d2", LV.LEN[side + "_d2"])
            self.st(c(end), 0)
        self.set(c("hendA"), c("na"))
        self.set(c("hendB"), c("nb"))
        for j, out in ((0, "yl"), (1, "yr")):
            self.fz(c(out))
            for kk in range(7 * j, 7 * j + 7):
                line, _t, sg = LV.TAPS[kk]
                self.rd_c(line, LV.TAPK[kk], 1)
                self.ld(0, c(out))
                p.fop(0, 0, "+" if sg > 0 else "-", 1)
                self.st(c(out), 0)
        for out, ptr in (("yl", "op_l"), ("yr", "op_r")):
            self.set(c(out), c(out) * k(LV.OUT_K))
            self.ptr(4, ptr)
            self.ld(0, c(out))
            p.sti(0, 4, 0)
            self.bump(ptr, 4)
        self.set(c("ma"), c("ma") + c("dma"))
        self.set(c("mb"), c("mb") + c("dmb"))
        p.ld(9, C["wi"])
        p.iconst(12, 1)
        p.iop(9, 9, "+", 12)
        p.iconst(12, LV.WMASK)
        p.iop(9, 9, "AND", 12)
        p.st(C["wi"], 9)
        self.bump("ip", 4)

    # -- RIFT v0.28: the same sample, its values in registers -----------------------------------------------
    # Floats in R0..R7, integers in R8..R15: R14 the write index (wi) for the whole sample; R9, R10, R12 the
    # address's; I1 a line's word, I4 the input and output words. Every float operation is live.Verb's, in its
    # order, on the same operands (the products' and sums' operand order only where IEEE gives the same bits).
    def _at(self, line: str, d=None, ireg: int = 1) -> None:
        """I<ireg> = line's word at (wi - d) & mask, as bytes: base + ((4 wi - 4 d) & (4 size - 1)) (R15 = 4 wi);
        D None (d 0), an int, or ("r", n) (d in Rn). The mask in R13, the base in R12: repeated, their loads
        are left out (Prog's known registers)"""
        p = self.p
        if d is None or (not isinstance(d, tuple) and d == 0):
            p.iconst(13, 4 * LV.SIZE[line] - 1)
            p.iop(9, 15, "AND", 13)
        else:
            if isinstance(d, tuple):
                p.lsh(10, d[1], 2)
            else:
                p.iconst(10, 4 * d)
            p.iop(9, 15, "-", 10)
            p.iconst(13, 4 * LV.SIZE[line] - 1)
            p.iop(9, 9, "AND", 13)
        p.iconst(12, self.L.line(line))
        p.iop(9, 9, "+", 12)
        p.seti(ireg, 9)

    def _ap_r(self, line: str, d: int, g: int) -> None:
        """F0 = live.ap(line, F0, d, Fg): z (F1), v = x - g z (F3) written, z + g v. Clobbers F1, F3"""
        p = self.p
        self._at(line, d)
        p.ldi(1, 0, 1)                          # z
        p.fop(3, g, "*", 1)
        p.fop(3, 0, "-", 3)                     # v = x - g z
        self._at(line)
        p.sti(0, 1, 3)
        p.fop(3, g, "*", 3)
        p.fop(0, 1, "+", 3)                     # z + g v

    def _apf_r(self, line: str) -> None:
        """F0 = live.apf(line, F0, F5, F7): di = trunc(d), fr = d - di, z = b0 + (b1 - b0) fr, as _ap_r.
        Clobbers F1..F3, F6, R11"""
        p = self.p
        p.trunc(11, 5)                          # di
        p.iconst(12, 0)
        p.float_(6, 11, 12)
        p.fop(6, 5, "-", 6)                     # fr = d - di
        self._at(line, ("r", 11))
        p.ldi(1, 0, 1)                          # b0
        p.lsh(10, 11, 2)
        p.iop(9, 15, "-", 10)
        p.iconst(10, 4)
        p.iop(9, 9, "-", 10)                    # 4 (wi - di - 1)
        p.iconst(13, 4 * LV.SIZE[line] - 1)
        p.iop(9, 9, "AND", 13)
        p.iconst(12, self.L.line(line))
        p.iop(9, 9, "+", 12)
        p.seti(1, 9)
        p.ldi(2, 0, 1)                          # b1
        p.fop(2, 2, "-", 1)
        p.fop(2, 2, "*", 6)
        p.fop(1, 1, "+", 2)                     # z = b0 + (b1 - b0) fr
        p.fop(3, 7, "*", 1)
        p.fop(3, 0, "-", 3)                     # v = x - g z
        self._at(line)
        p.sti(0, 1, 3)
        p.fop(3, 7, "*", 3)
        p.fop(0, 1, "+", 3)                     # z + g v

    def sample_fast(self) -> None:
        p, C = self.p, self.L.C
        p.ld(14, C["wi"])
        p.lsh(15, 14, 2)                        # 4 wi: the lines' byte offsets
        p.ld(12, C["ip"])
        p.seti(4, 12)
        p.ldi(0, 0, 4)                          # x
        p.iconst(12, 0x7FFFFFFF)
        p.iop(1, 0, "AND", 12)                  # |x|
        p.fconst(2, float(LV.IN_MAX))
        p.if_(1, "LT", 2, lambda: None, lambda: p.fconst(0, 0.0))
        self._at("pre")
        p.sti(0, 1, 0)                          # wr pre
        p.ld(11, C["pred"])
        p.ifz(11, "GT", lambda: (self._at("pre", ("r", 11)), p.ldi(0, 0, 1)))
        for name, g in (("i0", LV.GI1), ("i1", LV.GI1), ("i2", LV.GI2), ("i3", LV.GI2)):
            p.fconst(6, float(g))
            self._ap_r(name, LV.LEN[name], 6)
        p.ipass(4, 0)                           # x, kept for both sides (F4)
        for side, other, sh, end, m in (("a", "hendB", "hshA", "na", "ma"), ("b", "hendA", "hshB", "nb", "mb")):
            p.iconst(10, LV.LEN[side + "_ap"])
            p.iconst(12, 0)
            p.float_(5, 10, 12)
            p.ld(1, C[m])
            p.fop(5, 5, "+", 1)                 # dd = len + m
            p.ld(1, C["gdec"])
            p.ld(2, C[other])
            p.fop(1, 1, "*", 2)
            p.fop(0, 4, "+", 1)                 # x + gdec end
            p.fconst(7, float(LV.GD1))
            self._apf_r(side + "_ap")
            self._at(side + "_d1")
            p.sti(0, 1, 0)
            self._at(side + "_d1", LV.LEN[side + "_d1"])
            p.ldi(0, 0, 1)                      # t1
            p.ld(1, C[sh])                      # the shelf: hs += c_sh (t1 - hs)
            p.fop(2, 0, "-", 1)
            p.ld(3, C["c_sh"])
            p.fop(2, 3, "*", 2)
            p.fop(1, 1, "+", 2)
            p.st(C[sh], 1)
            p.fop(2, 0, "-", 1)                 # t1 = (hs + g_sh (t1 - hs)) gdec
            p.ld(3, C["g_sh"])
            p.fop(2, 3, "*", 2)
            p.fop(2, 1, "+", 2)
            p.ld(3, C["gdec"])
            p.fop(0, 2, "*", 3)
            p.ld(6, C["gd2"])
            self._ap_r(side + "_ap2", LV.LEN[side + "_ap2"], 6)
            self._at(side + "_d2")
            p.sti(0, 1, 0)
            self._at(side + "_d2", LV.LEN[side + "_d2"])
            p.ldi(0, 0, 1)
            p.st(C[end], 0)
        p.ld(0, C["na"])
        p.st(C["hendA"], 0)
        p.ld(0, C["nb"])
        p.st(C["hendB"], 0)
        p.fconst(3, float(LV.OUT_K))
        for j, ptr in ((0, "op_l"), (1, "op_r")):
            p.fconst(2, 0.0)
            for kk in range(7 * j, 7 * j + 7):
                line, _t, sg = LV.TAPS[kk]
                self._at(line, LV.TAPK[kk])
                p.ldi(1, 0, 1)
                p.fop(2, 2, "+" if sg > 0 else "-", 1)
            p.fop(2, 2, "*", 3)
            p.ld(12, C[ptr])
            p.seti(4, 12)
            p.sti(0, 4, 2)
            self.bump(ptr, 4)
        for m in ("ma", "mb"):
            p.ld(0, C[m])
            p.ld(1, C["d" + m])
            p.fop(0, 0, "+", 1)
            p.st(C[m], 0)
        p.iconst(12, 1)
        p.iop(9, 14, "+", 12)
        p.iconst(12, LV.WMASK)
        p.iop(9, 9, "AND", 12)
        p.st(C["wi"], 9)
        self.bump("ip", 4)


def body(p, L: Layout) -> MG:
    g = MG(p, L)
    saved = p.scr_on
    p.iconst(0, L.base5)
    p.seti(5, 0, "the scratch's base + WIN words")
    p.scr_on = True
    g.entry()
    p.scr_on = saved
    return g


def program(L: Layout, prefix: str = "mv") -> str:
    """the routine's assembly text: wr_mv, its routines and leaves"""
    p = FP_.FProg("emit", prefix=prefix)
    p.pool = {}
    p.spill = None
    p.scr = (L.scratch, L.scratch_end, L.base5)
    p.lines.append(f".GLOBAL wr_{prefix}.;")
    p.lines.append(f"wr_{prefix}.:")
    for k_, r in enumerate(SAVE):
        p.e(f"DM({L.save + 4 * k_:#x}) = {r};")
    g = body(p, L)
    for k_, r in enumerate(SAVE):
        p.e(f"{r} = DM({L.save + 4 * k_:#x});")
    p.e(f"JUMP {RESUME_SW:#x};", "the FX function, after the stock core's call")
    g.emit_rts()
    p.emit_subs()
    p.lines.append(f".wr_{prefix}..end:")
    p.lines.append(f"      .type wr_{prefix}.,STT_FUNC;")
    head = ["// mverb.asm -- RIFT's master reverb in the stock core's place (docs/master-reverb.md).",
            "// GENERATED by scripts/gen_mverb_asm.py from dnfw.mverb.program; do not edit by hand.", "",
            ".SECTION/PM seg_pmco;", ""]
    return "\n".join(head + p.lines) + "\n"


def run_block(L: Layout, read, mem=None):
    """the model: one block on memory READ (and MEM's earlier writes). -> (Prog, mem)"""
    mem = mem or Mem(read)
    p = FP_.FProg("run", mem=mem)
    p.pool = {}
    p.spill = None
    p.scr = (L.scratch, L.scratch_end, L.base5)
    body(p, L)
    return p, mem


def layout() -> Layout:
    from ..waverider import dsp
    return Layout(FP_.layout(), dsp.MVERB_DDR, dsp.MVERB_SAVE_DM)
