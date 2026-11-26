"""RUBBER's DSP program (RIFT v0.24, in GLASS's place: the FLTR type 6, on every machine): `dnfw.glass.live.Voice` on the
SHARC, in FASCIA's expression compiler with ORGAN's leaves (exp2f, expf, sin_turns, recip). The same
calls are the assembly text and, run in Python, its exact model; test_glass_program holds the run mode
to live.Voice bit for bit.

**Where it runs.** At the end of FASCIA's walk (fascia.asm), when every machine's buffer of the block
is whole and the stock per-track chain (gain, base/width filter, amp) has not yet run: for each slot
whose frame filter type is 6 (the frame's word 180 + 2 t; the DSP's own filter number is 0, "no
filter", so the chain skips its filter stage), the slot's buffer is filtered in place.

**Its settings** are the stock filter fields the unpack writes into the slot's record as floats
(`voice.TRACKS + 0x234 t`, live.FIELDS); its state (the four stages', the coefficient's, the envelope's) is in
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
FAST = True                            # RIFT v0.24: RUBBER's samples in registers (samples_fast); False: sample()
FILTER_HDR = 180                       # the frame's filter type a slot (dnfw.waverider.frame.FILTER)
REC_STRIDE = WV.TRACK_STRIDE

# -- a slot's state (DDR, 16 words) -----------------------------------------------------------------
ST = St().w("s1", "s2", "s3", "s4", "gp", "stage", "u", "env", "magic")
# RIFT v0.26 (fiddly_digits, 2026-11-25: "my track goes silent when I put RUBBER on it"): DDR is not
# cleared at power-on and GLASS's state never was: whatever lay there (a NaN, a huge value) went into the
# stages, the sanitizer zeroed the slot every block, and the state never recovered. A slot whose magic is
# not MAGIC starts from zeros (live.Voice's start), and the sanitizer clears the magic of a slot it zeroes.
MAGIC = 0x52554231                     # 'RUB1'
assert ST.n <= 16

_SRC = pathlib.Path(__file__).read_text(encoding="utf-8")
FIELD_WORDS = ("r_typ", "r_freq", "r_res", "r_atk", "r_dec", "r_abnd", "r_dbnd", "r_depth", "r_keyt")
WORDS = tuple(sorted(set(re.findall(r'\bc\("([A-Za-z_0-9]+)"\)', _SRC))
                     | {"trig", "nn", "gt", "gcnt", "rb", "sb", "bp", "icnt", "ocnt", "y1", "y2", "y3", "y4"} | set(FIELD_WORDS)))


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

        def fresh():                           # RIFT v0.26: a fresh state (live.Voice()), its magic set
            self.ptr(3, "sb")
            for name in ST.off:
                if name != "magic":
                    p.iconst(0, 0)
                    p.sti(ST[name], 3, 0)
            p.iconst(0, MAGIC)
            p.sti(ST["magic"], 3, 0)
        p.ldi(0, ST["magic"], 3)
        p.iconst(1, MAGIC)
        p.if_(0, "NE", 1, fresh, kind="i")
        self.ptr(3, "sb")
        # the envelope
        p.ld(0, C["trig"])

        def trig():
            self.ptr(3, "sb")
            self.iset(self.Si("stage"), 1)
            self.fz(S("u"))
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
        # the cutoff
        self.set(c("note"), c("r_freq") * k(128.0) + c("r_keyt") * (c("nn") - k(60.0)))
        self.ptr(3, "sb")
        self.set(c("note"), c("note") + ((c("r_depth") - k(0.5)) * k(144.0)) * S("env"))
        self.set(c("hz"), note_hz(c("note")))
        self.set(c("hz"), mn(mx(c("hz"), k(LV.F_MIN)), k(LV.F_MAX)))
        self.set(c("wt"), c("hz") * k(float(F(LV.PI_2FS * LV.INV_PI))))
        self.set(c("g"), sin_turns(c("wt")) * FP_.recip(sin_turns(c("wt") + k(0.25))))
        self.set(c("g1"), c("g") * FP_.recip(k(1.0) + c("g")))
        self.ptr(3, "sb")
        self.cmp(S("gp"), "GT", k(0.0), lambda: (self.ptr(3, "sb"), self.set(c("g0"), S("gp"))),
                 lambda: self.set(c("g0"), c("g1")))
        self.set(c("dg"), (c("g1") - c("g0")) * k(LV.INV_SUB))
        self.ptr(3, "sb")
        self.set(S("gp"), c("g1"))
        self.set(c("kq"), (c("r_res") * (k(0.7) + k(0.3) * c("r_res"))) * k(LV.K_MAX))
        self.set(c("g2"), c("g1") * c("g1"))
        self.set(c("den"), FP_.recip(k(1.0) + c("kq") * (c("g2") * c("g2"))))
        self.set(c("drive"), k(1.0) + c("r_typ") * k(LV.DRIVE_SPAN))
        self.set(c("ing"), c("drive") * (k(1.0) + c("kq") * k(LV.COMP)))
        self.set(c("outg"), FP_.recip(k(0.6) + k(0.4) * c("drive")))
        # the state into words, the samples, the state back
        self.ptr(3, "sb")
        for n in ("s1", "s2", "s3", "s4"):
            self.set(c(n), S(n))
        self.set(c("gg"), c("g0"))
        p.ld(9, L.t_word)
        p.lsh(12, 9, 2)
        p.iconst(11, BUFFERS)
        p.iop(12, 11, "+", 12)
        p.seti(1, 12)
        p.ldi(0, 0, 1)
        p.st(C["bp"], 0)
        if FAST:
            self.samples_fast()
        else:
            p.loop(C["icnt"], BLOCK, lambda: self.rt("g_tick", self.sample))
        self.ptr(3, "sb")
        for n in ("s1", "s2", "s3", "s4"):
            self.set(S(n), c(n))

    def samples_fast(self) -> None:
        """sample()'s 32 samples with the stages, the coefficient and the block's constants in registers: the
        same operations on the same operands in the same order (the same bits), a third of the cost.
        R2..R5 s1..s4, R6 gg, R7 dg, R8 kq, R9 den, R10 ing, R11 outg; R0 R1 R12 R13 R14 scratch; R15 the
        count; I4 the buffer."""
        p, C = self.p, self.L.C
        for r, n in ((2, "s1"), (3, "s2"), (4, "s3"), (5, "s4"), (6, "gg"), (7, "dg"), (8, "kq"), (9, "den"),
                     (10, "ing"), (11, "outg")):
            p.ld(r, C[n])
        self.ptr(4, "bp")

        def sat0():                                  # R0 = live.sat(R0)
            def mid():
                p.fop(1, 0, "*", 0)                  # x2
                p.fconst(13, 27.0)
                p.fop(13, 13, "+", 1)                # 27 + x2
                p.fop(13, 0, "*", 13)                # x (27 + x2)
                p.fconst(14, 9.0)
                p.fop(14, 14, "*", 1)                # 9 x2
                p.fconst(12, 27.0)
                p.fop(14, 12, "+", 14)               # 27 + 9 x2
                FP_._recip_body(p, 14, 1, 0)         # R1 = recip(R14)
                p.fop(0, 13, "*", 1)
            p.fconst(1, float(LV.SAT3))

            def low():
                p.fconst(1, -3.0)
                p.if_(0, "LE", 1, lambda: p.fconst(0, -1.0), mid)
            p.if_(0, "GE", 1, lambda: p.fconst(0, 1.0), low)

        def one():
            p.fop(6, 6, "+", 7)                      # gg += dg
            p.fconst(1, 1.0)
            p.fop(1, 1, "-", 6)                      # om
            p.fop(12, 6, "*", 6)                     # q2
            p.fop(13, 12, "*", 6)                    # q3
            p.fop(13, 13, "*", 2)                    # q3 s1
            p.fop(12, 12, "*", 3)                    # q2 s2
            p.fop(13, 13, "+", 12)
            p.fop(12, 6, "*", 4)                     # gg s3
            p.fop(13, 13, "+", 12)
            p.fop(13, 13, "+", 5)                    # + s4
            p.fop(13, 13, "*", 1)                    # sm
            p.ldi(0, 0, 4)                           # x
            p.fop(0, 0, "*", 10)                     # x ing
            p.fop(13, 8, "*", 13)                    # kq sm
            p.fop(0, 0, "-", 13)
            p.fop(0, 0, "*", 9)                      # u
            sat0()
            for s in (2, 3, 4, 5):
                p.fop(12, 0, "-", s)                 # prev - s
                p.fop(12, 6, "*", 12)                # gg (..)
                p.fop(0, s, "+", 12)                 # y
                p.fconst(13, 2.0)
                p.fop(13, 13, "*", 0)                # 2 y
                p.fop(s, 13, "-", s)                 # s = 2 y - s
            p.fop(0, 0, "*", 11)                     # y4 outg
            p.stpost(4, 0)
        p.loop_r(15, BLOCK, one)
        for r, n in ((2, "s1"), (3, "s2"), (4, "s3"), (5, "s4")):
            p.st(C[n], r)

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

    def sat(self, m: Mv) -> None:
        """m = live.sat(m)"""
        c = self.c

        def mid():
            self.set(c("x2"), m * m)
            self.set(m, (m * (k(27.0) + c("x2"))) * FP_.recip(k(27.0) + k(9.0) * c("x2")))
        self.cmp(m, "GE", k(LV.SAT3), lambda: self.set(m, k(1.0)),
                 lambda: self.cmp(m, "LE", k(-3.0), lambda: self.set(m, k(-1.0)), mid))

    def sample(self) -> None:
        p, c = self.p, self.c
        self.ptr(4, "bp")
        self.set(c("xi"), Mv("i", 4, 0))
        self.set(c("gg"), c("gg") + c("dg"))
        self.set(c("om"), k(1.0) - c("gg"))
        self.set(c("q2"), c("gg") * c("gg"))
        self.set(c("q3"), c("q2") * c("gg"))
        self.set(c("sm"), ((((c("q3") * c("s1")) + c("q2") * c("s2")) + c("gg") * c("s3")) + c("s4")) * c("om"))
        self.set(c("uu"), ((c("xi") * c("ing")) - c("kq") * c("sm")) * c("den"))
        self.sat(c("uu"))
        prev = "uu"
        for n in ("s1", "s2", "s3", "s4"):
            yn = "y" + n[1]
            self.set(c(yn), c(n) + c("gg") * (c(prev) - c(n)))
            self.set(c(n), k(2.0) * c(yn) - c(n))
            prev = yn
        self.ptr(4, "bp")
        self.set(Mv("i", 4, 0), c("y4") * c("outg"))
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
