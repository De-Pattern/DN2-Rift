"""GLASS's DSP program (RIFT v0.18: the FLTR type 6, on every machine): `dnfw.glass.live.Voice` on the
SHARC, in FASCIA's expression compiler with ORGAN's leaves (exp2f, expf, sin_turns, recip). The same
calls are the assembly text and, run in Python, its exact model; test_glass_program holds the run mode
to live.Voice bit for bit.

**Where it runs.** At the end of FASCIA's walk (fascia.asm), when every machine's buffer of the block
is whole and the stock per-track chain (gain, base/width filter, amp) has not yet run: for each slot
whose frame filter type is 6 (the frame's word 180 + 2 t; the DSP's own filter number is 0, "no
filter", so the chain skips its filter stage), the slot's buffer is filtered in place.

**Its settings** are the stock filter fields the unpack writes into the slot's record as floats
(`voice.TRACKS + 0x234 t`, live.FIELDS); its state (the filter's, the envelope's, the vactrol's) is in
DDR at GLASS_STATE + 64 t (16 words a slot), loaded and stored once a block.
"""
from __future__ import annotations

import pathlib
import re

import numpy as np

from ..fascia import program as FP_
from ..fascia.program import E, Kc, Mv, St, w, mn, mx, ab, BLOCK, BUFFERS
from ..organ import program as OP
from ..organ.program import exp2f, expf, sin_turns
from ..perc import program as PP
from ..perc.dsl import Mem
from ..waverider import voice as WV
from . import live as LV

F = np.float32
assert BLOCK == LV.SUB
FAST = True                            # RIFT v0.22: the samples in registers (samples_fast); False: v0.18..v0.21's sample()
FILTER_HDR = 180                       # the frame's filter type a slot (dnfw.waverider.frame.FILTER)
REC_STRIDE = WV.TRACK_STRIDE

# -- a slot's state (DDR, 16 words) -----------------------------------------------------------------
ST = St().w("s1", "s2", "lowz", "stage", "u", "env", "vac", "vtarget")
assert ST.n <= 16

_SRC = pathlib.Path(__file__).read_text(encoding="utf-8")
FIELD_WORDS = ("r_typ", "r_freq", "r_res", "r_lpg", "r_atk", "r_dec", "r_abnd", "r_dbnd", "r_depth", "r_keyt")
WORDS = tuple(sorted(set(re.findall(r'\bc\("([A-Za-z_0-9]+)"\)', _SRC))
                     | {"trig", "nn", "gt", "gcnt", "rb", "sb", "bp", "icnt", "ocnt"} | set(FIELD_WORDS)))


def k(x) -> Kc:
    return Kc(float(F(x)))


class Layout:
    def __init__(self, fascia: FP_.Layout, state: int):
        self.fl = fascia
        self.t_word = fascia.C["t"]
        self.state = state
        at = fascia.arrays
        self.C = {}
        for name in WORDS:
            self.C[name] = at
            at += 4
        self.A = {}
        self.words_end = at
        assert at <= fascia.scratch_end, (at - fascia.scratch_end, "GLASS's words must fit in FASCIA's arrays")
        self.scratch, self.scratch_end, self.base5 = fascia.scratch, fascia.scratch_end, fascia.base5
        self.rets = fascia.rets


def note_hz(n) -> E:
    return k(440.0) * exp2f((n - k(69.0)) * k(float(F(F(1.0) / F(12.0)))))


class GG(OP.OG):
    """FASCIA's compiler with ORGAN's leaves, on a slot's GLASS state (I3 = its DDR record)"""

    def c(self, name) -> Mv:
        return Mv("a", self.L.C[name])

    def S(self, name) -> Mv:
        return Mv("i", 3, ST[name])

    def Si(self, name) -> Mv:
        return Mv("i", 3, ST[name], isint=True)

    def bump(self, word: str, by: int) -> None:
        p, C = self.p, self.L.C
        p.ld(13, C[word])
        p.iconst(12, by)
        p.iop(13, 12, "+", 13)
        p.st(C[word], 13)

    def ptr(self, ireg: int, word: str) -> None:
        self.p.ld(12, self.L.C[word])
        self.p.seti(ireg, 12)

    # -- the pass: every slot, those on GLASS ---------------------------------------------------------
    def walk(self) -> None:
        p, C, L = self.p, self.L.C, self.L
        p.iconst(0, 0)
        p.st(C["gt"], 0)

        def one():
            p.ld(9, C["gt"])
            p.iop(10, 9, "+", 9)
            PP.half(p, 4, FILTER_HDR, 10)
            p.iconst(12, LV.FILTER_TYPE)

            def mine():
                p.ld(9, C["gt"])
                p.st(L.t_word, 9)
                self.rt("g_slot", self.slot)
            p.if_(4, "EQ", 12, mine, kind="i")
            self.bump("gt", 1)
        p.loop(C["gcnt"], 16, one)

    def slot(self) -> None:
        """live.Voice.block for slot t (L.t_word)"""
        p, C, L = self.p, self.L.C, self.L
        c, S = self.c, self.S
        self.read_note()
        # the record's floats
        p.ld(9, L.t_word)
        p.iconst(12, REC_STRIDE)
        p.mul_ssi(9, 9, 12)
        p.iconst(12, WV.TRACKS)
        p.iop(9, 9, "+", 12)
        p.st(C["rb"], 9)
        for name, off in zip(FIELD_WORDS, LV.FIELDS):
            self.ptr(4, "rb")
            p.ldi(0, off // 4, 4)
            p.st(C[name], 0)
        # the state's record (DDR)
        p.ld(9, L.t_word)
        p.lsh(9, 9, 6)
        p.iconst(12, L.state)
        p.iop(9, 9, "+", 12)
        p.st(C["sb"], 9)
        self.ptr(3, "sb")
        # the envelope
        p.ld(0, C["trig"])

        def trig():
            self.ptr(3, "sb")
            self.iset(self.Si("stage"), 1)
            self.fz(S("u"))
            self.set(S("vtarget"), k(1.0))
        p.ifz(0, "NE", trig)
        self.ptr(3, "sb")
        self.set(c("atk"), k(0.0001) * exp2f(c("r_atk") * k(12.0)))
        self.set(c("dec"), k(0.002) * exp2f(c("r_dec") * k(12.3)))
        self.ptr(3, "sb")

        def attack():
            self.ptr(3, "sb")
            self.set(S("u"), S("u") + k(LV.BLK) * FP_.recip(c("atk")))

            def to_decay():
                self.ptr(3, "sb")
                self.iset(self.Si("stage"), 2)
                self.fz(S("u"))
                self.set(S("env"), k(1.0))

            def bent():
                self.bend("bd", S("u"), c("r_abnd"))
                self.ptr(3, "sb")
                self.set(S("env"), c("bd"))
            self.ptr(3, "sb")
            self.cmp(S("u"), "GE", k(1.0), to_decay, bent)

        def decay():
            self.ptr(3, "sb")
            self.set(S("u"), S("u") + k(LV.BLK) * FP_.recip(c("dec")))

            def to_off():
                self.ptr(3, "sb")
                self.iset(self.Si("stage"), 0)
                self.fz(S("u"))
                self.fz(S("env"))

            def bent():
                self.bend("bd", S("u"), c("r_dbnd"))
                self.ptr(3, "sb")
                self.set(S("env"), k(1.0) - c("bd"))
            self.ptr(3, "sb")
            self.cmp(S("u"), "GE", k(1.0), to_off, bent)
        self.ptr(3, "sb")
        self.icmp(self.Si("stage"), "EQ", 1, attack,
                  lambda: (self.ptr(3, "sb"), self.icmp(self.Si("stage"), "EQ", 2, decay,
                                                        lambda: (self.ptr(3, "sb"), self.fz(S("env"))))))
        # LPG's vactrol
        self.ptr(3, "sb")
        self.set(c("v0"), S("vac"))

        def lpg_on():
            def rise():
                self.ptr(3, "sb")
                self.set(S("vac"), S("vac") + k(LV.LPG_STEP) * (S("vtarget") - S("vac")))
                self.ptr(3, "sb")
                self.cmp(S("vac"), "GT", k(0.98) * S("vtarget"), lambda: (self.ptr(3, "sb"), self.fz(S("vtarget"))))

            def fall():
                self.ptr(3, "sb")
                self.set(c("cl"), k(1.0) - S("vac"))
                self.set(c("vtau"), c("dec") * (k(0.15) + k(0.85) * (c("cl") * c("cl"))))
                self.ptr(3, "sb")
                self.set(S("vac"), S("vac") * expf(k(0.0) - k(LV.BLK) * FP_.recip(c("vtau"))))
            self.ptr(3, "sb")
            self.cmp(S("vtarget"), "GT", S("vac"), rise, fall)

        def lpg_off():
            self.ptr(3, "sb")
            self.set(S("vac"), k(1.0))
            self.fz(S("vtarget"))
        self.cmp(c("r_lpg"), "GE", k(0.5), lpg_on, lpg_off)
        # the cutoff
        self.ptr(3, "sb")
        self.set(c("note"), c("r_freq") * k(128.0) + c("r_keyt") * (c("nn") - k(60.0)))
        self.set(c("note"), c("note") + ((c("r_depth") - k(0.5)) * k(144.0)) * S("env"))
        self.cmp(c("r_lpg"), "GE", k(0.5),
                 lambda: (self.ptr(3, "sb"), self.set(c("note"), k(20.0) + (c("note") - k(20.0)) * S("vac"))))
        self.set(c("hz"), note_hz(c("note")))
        self.set(c("hz"), mn(mx(c("hz"), k(LV.F_MIN)), k(LV.F_MAX)))
        self.set(c("wt"), c("hz") * k(float(F(LV.PI_2FS * LV.INV_PI * F(0.5)))))
        self.set(c("g"), sin_turns(c("wt")) * FP_.recip(sin_turns(c("wt") + k(0.25))))
        self.set(c("rs"), c("r_res") * (k(0.7) + k(0.3) * c("r_res")))
        self.set(c("tau"), k(0.004) * exp2f(c("rs") * k(9.96578428)))
        self.set(c("q"), mx((k(3.14159265) * c("hz")) * c("tau"), k(0.5)))
        self.set(c("kk"), FP_.recip(c("q")))
        self.set(c("a1"), FP_.recip(k(1.0) + c("g") * (c("g") + c("kk"))))
        self.set(c("drive"), k(1.0) - k(0.45) * (c("r_res") * c("r_res")))
        self.set(c("idrive"), FP_.recip(c("drive")))
        self.set(c("lp1"), k(1.0) - expf(k(0.0) - k(LV.TWOPI_FS) * c("hz")))
        self.set(c("keep"), k(0.5) * c("r_res"))
        self.cmp(c("r_res"), "LT", k(0.3), lambda: self.set(c("keep"), c("keep") * (c("r_res") * k(float(F(1.0 / 0.3))))))
        self.set(c("kb"), c("kk") * k(LV.SQRT2))

        def lev_lpg():
            self.ptr(3, "sb")
            self.set(c("lev0"), c("v0"))
            self.set(c("lev1"), S("vac"))

        def lev_flat():
            self.set(c("lev0"), k(1.0))
            self.set(c("lev1"), k(1.0))
        self.cmp(c("r_lpg"), "GE", k(0.5), lev_lpg, lev_flat)
        self.set(c("dlev"), (c("lev1") - c("lev0")) * k(LV.INV_SUB))
        self.set(c("lev"), c("lev0"))
        # the state into words, the samples, the state back
        self.ptr(3, "sb")
        self.set(c("s1"), S("s1"))
        self.set(c("s2"), S("s2"))
        self.set(c("lowz"), S("lowz"))
        p.ld(9, L.t_word)
        p.lsh(12, 9, 2)
        p.iconst(11, BUFFERS)
        p.iop(12, 11, "+", 12)
        p.seti(1, 12)
        p.ldi(0, 0, 1)
        p.st(C["bp"], 0)
        if FAST:
            self.samples_fast()
            return
        p.loop(C["icnt"], BLOCK, self.sample)
        self.ptr(3, "sb")
        self.set(S("s1"), c("s1"))
        self.set(S("s2"), c("s2"))
        self.set(S("lowz"), c("lowz"))

    def samples_fast(self) -> None:
        """RIFT v0.22 (the owner, 2026-11-23: GLASS "weirdly bitcrushed, like the Monomachine's overload"):
        sample()'s 32 samples with the filter's state, the cutoff's coefficients and the level in registers.
        The same operations on the same operands in the same order as sample() (float32 after each, the
        core's RND32): the same bits, at about a quarter of the cost (sample() loaded and stored every
        intermediate; on fifteen tracks GLASS took 108k cycles a block and ran the frame over).

        R2 s1, R3 s2, R13 lowz, R14 lev, R7 g, R8 a1, R9 2.0, R10 KNEE, R11 the abs mask; R4 xin (then hp),
        R5 v1 (then bp), R6 v2 (then lp); R0 R1 R12 scratch; R15 the count; I4 the buffer, I3 the state."""
        p, C = self.p, self.L.C
        self.ptr(3, "sb")
        p.ldi(2, ST["s1"], 3)
        p.ldi(3, ST["s2"], 3)
        p.ldi(13, ST["lowz"], 3)
        p.ld(14, C["lev"])
        p.ld(7, C["g"])
        p.ld(8, C["a1"])
        p.fconst(9, 2.0)
        p.fconst(10, float(LV.KNEE))
        p.iconst(11, 0x7FFFFFFF)
        self.ptr(4, "bp")

        def knee():                                  # R2 = live.knee(R2); R0 = |R2|
            p.iop(0, 2, "AND", 11)

            def over():
                p.fconst(1, float(LV.KNEE3))

                def top():
                    p.fconst(12, 0.0)
                    p.if_(2, "GT", 12, lambda: p.fconst(2, float(LV.KNEE2)),
                          lambda: p.fconst(2, float(F(F(0.0) - LV.KNEE2))))

                def bend_():
                    p.fop(1, 0, "-", 10)             # kd = ka - KNEE
                    p.fop(1, 1, "*", 1)              # kd kd
                    p.fconst(12, float(LV.INV4K))
                    p.fop(1, 1, "*", 12)             # (kd kd) INV4K
                    p.fop(1, 0, "-", 1)              # ky = ka - that
                    p.fconst(12, 0.0)
                    p.if_(2, "GT", 12, lambda: p.fpass(2, 1), lambda: p.fop(2, 12, "-", 1))
                p.if_(0, "GE", 1, top, bend_)
            p.if_(0, "LE", 10, lambda: None, over)

        def step():
            p.fop(0, 4, "-", 3)                      # v3 = xin - s2
            p.fop(0, 7, "*", 0)                      # g v3
            p.fop(0, 2, "+", 0)                      # s1 + g v3
            p.fop(5, 8, "*", 0)                      # v1 = a1 (..)
            p.fop(0, 7, "*", 5)                      # g v1
            p.fop(6, 3, "+", 0)                      # v2 = s2 + g v1
            p.fop(0, 9, "*", 5)                      # 2 v1
            p.fop(2, 0, "-", 2)                      # s1 = 2 v1 - s1
            knee()
            p.fop(0, 9, "*", 6)                      # 2 v2
            p.fop(3, 0, "-", 3)                      # s2 = 2 v2 - s2

        def one():
            p.ldi(0, 0, 4)                           # xi
            p.st(C["xi"], 0)
            p.ld(1, C["drive"])
            p.fop(4, 0, "*", 1)                      # xin = xi drive
            step()
            step()
            p.ld(1, C["kk"])
            p.fop(0, 1, "*", 5)                      # kk v1
            p.fop(0, 4, "-", 0)                      # xin - kk v1
            p.fop(0, 0, "-", 6)                      # .. - v2
            p.ld(1, C["idrive"])
            p.fop(4, 0, "*", 1)                      # hp
            p.fop(5, 5, "*", 1)                      # bp
            p.fop(6, 6, "*", 1)                      # lp
            p.ld(0, C["xi"])
            p.fop(0, 0, "-", 13)                     # xi - lowz
            p.ld(1, C["lp1"])
            p.fop(0, 1, "*", 0)
            p.fop(13, 13, "+", 0)                    # lowz
            p.fop(0, 13, "-", 6)                     # lowz - lp
            p.ld(1, C["keep"])
            p.fop(0, 1, "*", 0)
            p.fop(6, 6, "+", 0)                      # lp + keep (lowz - lp)
            p.ld(12, C["kb"])
            p.fop(5, 5, "*", 12)                     # bp kb
            p.ld(0, C["r_typ"])
            p.fconst(1, 0.5)

            def low():
                p.fop(0, 0, "*", 9)                  # tt = typ 2
                p.fconst(1, 1.0)
                p.fop(1, 1, "-", 0)                  # 1 - tt
                p.fop(1, 1, "*", 6)                  # (1 - tt) lp
                p.fop(0, 0, "*", 5)                  # tt (bp kb)
                p.fop(0, 1, "+", 0)

            def high():
                p.fop(0, 0, "-", 1)                  # typ - 0.5
                p.fop(0, 0, "*", 9)                  # tt
                p.fconst(1, 1.0)
                p.fop(1, 1, "-", 0)                  # 1 - tt
                p.fop(1, 1, "*", 5)                  # (1 - tt) (bp kb)
                p.fop(0, 0, "*", 4)                  # tt hp
                p.fop(0, 1, "+", 0)
            p.if_(0, "LE", 1, low, high)
            p.fop(0, 0, "*", 14)                     # o lev
            p.stpost(4, 0)
            p.ld(1, C["dlev"])
            p.fop(14, 14, "+", 1)                    # lev + dlev
        p.loop_r(15, BLOCK, one)
        self.ptr(3, "sb")
        p.sti(ST["s1"], 3, 2)
        p.sti(ST["s2"], 3, 3)
        p.sti(ST["lowz"], 3, 13)

    def bend(self, dst: str, u: Mv, b: Mv) -> None:
        """c(dst) = live.bend(u, b): one routine (g_bend) on bu, bc, into bd"""
        c = self.c
        assert dst == "bd"
        self.set(c("bu"), u)
        self.set(c("bc"), b - k(0.5))
        self.rt("g_bend", self.bend_body)

    def bend_body(self) -> None:
        c = self.c
        dst = "bd"

        def bent():
            self.set(c("bk"), k(12.0) * ab(c("bc")))
            self.set(c("bden"), FP_.recip(expf(c("bk")) - k(1.0)))
            self.cmp(c("bc"), "LT", k(0.0),
                     lambda: self.set(c(dst), (expf(c("bk") * c("bu")) - k(1.0)) * c("bden")),
                     lambda: self.set(c(dst), k(1.0) - (expf(c("bk") * (k(1.0) - c("bu"))) - k(1.0)) * c("bden")))
        self.cmp(ab(c("bc")), "LT", k(0.004), lambda: self.set(c(dst), c("bu")), bent)

    def knee(self, m: Mv) -> None:
        """m = live.knee(m)"""
        c = self.c
        self.set(c("ka"), ab(m))

        def over():
            def top():
                self.cmp(m, "GT", k(0.0), lambda: self.set(m, k(LV.KNEE2)), lambda: self.set(m, k(0.0) - k(LV.KNEE2)))

            def bend_():
                self.set(c("kd"), c("ka") - k(LV.KNEE))
                self.set(c("ky"), c("ka") - (c("kd") * c("kd")) * k(LV.INV4K))
                self.cmp(m, "GT", k(0.0), lambda: self.set(m, c("ky")), lambda: self.set(m, k(0.0) - c("ky")))
            self.cmp(c("ka"), "GE", k(LV.KNEE3), top, bend_)
        self.cmp(c("ka"), "LE", k(LV.KNEE), lambda: None, over)

    def sample(self) -> None:
        p, c = self.p, self.c
        self.ptr(4, "bp")
        self.set(c("xi"), Mv("i", 4, 0))
        self.set(c("xin"), c("xi") * c("drive"))
        def step():                              # twice the rate, the input held
            self.set(c("v3"), c("xin") - c("s2"))
            self.set(c("v1"), c("a1") * (c("s1") + c("g") * c("v3")))
            self.set(c("v2"), c("s2") + c("g") * c("v1"))
            self.set(c("s1"), k(2.0) * c("v1") - c("s1"))
            self.knee(c("s1"))
            self.set(c("s2"), k(2.0) * c("v2") - c("s2"))
        p.loop(self.L.C["ocnt"], 2, step)
        self.set(c("lp"), c("v2") * c("idrive"))
        self.set(c("bpo"), c("v1") * c("idrive"))
        self.set(c("hp"), ((c("xin") - c("kk") * c("v1")) - c("v2")) * c("idrive"))
        self.set(c("lowz"), c("lowz") + c("lp1") * (c("xi") - c("lowz")))
        self.set(c("lp"), c("lp") + c("keep") * (c("lowz") - c("lp")))

        def low():
            self.set(c("tt"), c("r_typ") * k(2.0))
            self.set(c("o"), (k(1.0) - c("tt")) * c("lp") + c("tt") * (c("bpo") * c("kb")))

        def high():
            self.set(c("tt"), (c("r_typ") - k(0.5)) * k(2.0))
            self.set(c("o"), (k(1.0) - c("tt")) * (c("bpo") * c("kb")) + c("tt") * c("hp"))
        self.cmp(c("r_typ"), "LE", k(0.5), low, high)
        self.ptr(4, "bp")
        self.set(Mv("i", 4, 0), c("o") * c("lev"))
        self.set(c("lev"), c("lev") + c("dlev"))
        self.bump("bp", 4)


def walk(p, L: Layout) -> GG:
    """the pass over every slot, inside FASCIA's walk's tail (I5 is FASCIA's scratch base)"""
    g = GG(p, L)
    saved = p.scr_on
    p.iconst(0, L.base5)
    p.seti(5, 0, "the scratch's base + WIN words")
    p.scr_on = True
    g.walk()
    p.scr_on = saved
    return g


def run_slot(L: Layout, read, t: int, mem=None):
    """the model: slot T's block (as if its filter type were GLASS) on memory READ"""
    mem = mem or Mem(read)
    p = FP_.FProg("run", mem=mem)
    p.pool = {}
    p.spill = None
    p.scr = (L.scratch, L.scratch_end, L.base5)
    g = GG(p, L)
    p.iconst(0, L.base5)
    p.seti(5, 0)
    p.scr_on = True
    p.iconst(9, t)
    p.st(L.t_word, 9)
    g.slot()
    return p, mem


def run_walk(L: Layout, read, mem=None):
    mem = mem or Mem(read)
    p = FP_.FProg("run", mem=mem)
    p.pool = {}
    p.spill = None
    p.scr = (L.scratch, L.scratch_end, L.base5)
    walk(p, L)
    return p, mem


def layout() -> Layout:
    from ..waverider import dsp
    return Layout(FP_.layout(), dsp.GLASS_STATE_DDR)
