"""SILT's DSP program (machine type 20): `dnfw.silt.live.SlotVoice` on the SHARC, in PERC's two-backend
DSL on FASCIA's expression compiler (ORGAN's OG, with ORGAN's sine and its seeds' arithmetic): the same
calls are the assembly text and, run in Python, its exact model. test_silt_program holds the run mode
to live.SlotVoice bit for bit; the SHARC runner's `silt` part holds the assembled code to the run mode.

**Where it runs.** Inside FASCIA's program (fascia.asm, `wr_fsc`), as ORGAN does: FASCIA's walk renders
a slot whose frame type word is 20 with this, under the same frame guard and steal bookkeeping. A slot
is one machine or another: SILT's voice lives in the slot's FASCIA state (its life words FASCIA's first
three), and the walk's type change clears its magic, which makes the next block a fresh voice that
clears its lines (live.Voice.become).

**Memory.** The voice's words in the slot's state (L2); the block's words in FASCIA's transient arrays
(scratch, L1), as ORGAN's; the lines (live.Voice.lines: the waveguide's two, the eight filaments') in
DDR at SILT_DELAY_DDR + 0xC000 t; the per-player constants and the slots' seeds in DDR (SILT_TABLES).

**The note-off** is the frame's mask 36 (word 0x25c4b0, low half, bit t: the mask that releases the
DN2's own amp envelope, docs/cz.md); the trig mask 32's high half, the note and velocity as ORGAN's.
"""
from __future__ import annotations

import re
import pathlib
import struct

import numpy as np

from ..fascia import program as FP_
from ..fascia.program import (E, Kc, Mv, Fn, St, w, fi, recip, exp2, tanh, sqrt, mn, mx, ab, LEAF, _leaf,
                              _horner, _recip_body, _xs_leaf, STRIDE, BLOCK, BUFFERS, TRIG_WORD, NOTE_OFFSET)
from ..organ import program as OP
from ..perc import program as PP
from ..perc.dsl import Mem, f32, bits, flt
from . import live as LV

F = np.float32
TYPE = 20
NK = len(LV.CONTROLS)
assert NK == 32 and BLOCK == LV.SUB
OFF_WORD = 0x25C4B0                          # the frame's mask 36: the note-off, low half, bit t
MAGIC = 0x53494C54                           # 'SILT': the state was written by this program

# -- the voice's words (in the slot's FASCIA state: the life words are FASCIA's first three) -------
VOICE = St().w("on", "pending", "fading")
assert [VOICE[k] for k in ("on", "pending", "fading")] == [FP_.VOICE[k] for k in ("on", "pending", "fading")]
VOICE.w("magic", "rs1", "rs2", "rest", "fadef", "clear_at", "wait", "wnote", "wvel", "woff", "gate",
        "wb", "wk", "p_n", "p_i", "g_cnt",
        "lp", "bow", "hp", "fm1", "fm2", "env_e", "amp", "sk_dx", "sk_dy", "sk_Es", "sk_lp", "sk_E",
        "sk_s1", "sk_s2", "p_a", "aval", "prev_tgt", "loop_t", "qph", "cl_hp", "cl_b", "mo_c",
        "h1", "h2", "h3", "h4", "hx1", "hx2", "hx3", "hx4", "f_ax", "f_ay", "g_hold", "t_note",
        "part_t", "burst", "strike", "sq", "vib_ph", "vib_env", "gl_amt", "loop_per", "f0", "vel", "simp")
VOICE.w("L4", n=8).w("body", n=8).w("md", n=12).w("bub_f", n=4).w("bub_a", n=4).w("bub_p", n=4) \
    .w("bub_r", n=4).w("wnd", n=16).w("sk_ap", n=8)
# the players' words, one array each (I3 = the voice + 4 k addresses player k's)
FIL = ("slp", "sbow", "soff", "sdx", "sdy", "sd0", "sd1", "svph", "sdel", "scnt", "sw")
for _n in FIL:
    VOICE.w(_n, n=LV.NSEC)
VOICE_WORDS = VOICE.n
assert 4 * VOICE_WORDS <= STRIDE, VOICE_WORDS
assert VOICE["magic"] != OP.VOICE["magic"] or True

# -- the tables (DDR): the players' constants, the materials' modes, the slots' seeds ------------
TAB = {}
_at = 0
for _name, _vals in (("FACK", LV.FACK), ("IMPK", LV.IMPK), ("SGNK", LV.SGNK), ("ALTK", LV.ALTK),
                     ("HARM", LV.HARM), ("KF", tuple(F(k) for k in range(8)))):
    TAB[_name] = (_at, _vals)
    _at += len(_vals)
TABLE_WORDS = _at
LINE_STRIDE = 4 * LV.LINE_WORDS              # 48 KB a slot
assert LINE_STRIDE == 0xC000


def tables_bytes() -> bytes:
    vals = []
    for name, (at, v) in TAB.items():
        assert at == len(vals)
        vals += [bits(f32(float(x))) for x in v]
    return struct.pack(f"<{len(vals)}I", *vals)


def k(x) -> Kc:
    return Kc(float(F(x)))


KNOB_WORDS = ("part", "tens", "mass", "cohe", "visc", "grain", "dens", "bodyk",
              "press", "speedk", "pos", "rosin", "scrap", "snap", "air", "inst",
              "spread", "voices", "drift", "vibr", "glissk", "form", "rough", "morph")

# -- the words of the block (FASCIA's transient arrays): every c("...") of this file ------------
_SRC = pathlib.Path(__file__).read_text(encoding="utf-8")
WORDS = tuple(sorted(set(re.findall(r'\bc\("([A-Za-z_0-9]+)"\)', _SRC)) | set(re.findall(r'\bci\("([A-Za-z_0-9]+)"\)', _SRC))
                     | set(re.findall(r'\bC\["([A-Za-z_0-9]+)"\]', _SRC))
                     | {"trig", "nn", "k146", "tmp0", "tmp1", "cc", "lg_e", "lg_t", "off", "tvel", "cnt0", "cnt1",
                        "cnt2", "outp", "bad", "kfl", "lnp"} | {f"e{j}" for j in range(NK)} | set(KNOB_WORDS)))
ARRAYS = {"yb": BLOCK, "sper": LV.NSEC, "bc": 4, "bs": 4, "mc": 6, "ms": 6, "wpos": 6}


class Layout:
    def __init__(self, fascia: FP_.Layout, tables: int, lines: int):
        self.fl = fascia
        self.state, self.state2 = fascia.state, fascia.state2
        self.t_word = fascia.C["t"]
        self.stolen, self.strikes = fascia.stolen, fascia.strikes
        self.tables, self.lines = tables, lines
        at = fascia.arrays
        self.C = {}
        for name in WORDS:
            self.C[name] = at
            at += 4
        for name in ("tanh_x", "tanh_n"):      # FASCIA's leaves' own words (the leaves are FASCIA's code)
            self.C[name] = fascia.C[name]
        self.A = {}
        for name, n in ARRAYS.items():
            self.A[name] = at
            at += 4 * n
        self.words_end = at
        assert at <= fascia.scratch_end, (at - fascia.scratch_end, "SILT's words must fit in FASCIA's arrays")
        self.scratch, self.scratch_end, self.base5 = fascia.scratch, fascia.scratch_end, fascia.base5
        self.rets = fascia.rets


# -- leaves --------------------------------------------------------------------------------------
def _s_log2(g) -> None:
    """live.log2f (F15 in and out; R12-R15 and two scratch words)"""
    p, C = g.p, g.L.C

    def body():
        def rest():
            p.lsh(14, 15, -23)
            p.iconst(13, 0xFF)
            p.iop(14, 14, "AND", 13)
            p.iconst(13, 127)
            p.iop(14, 14, "-", 13)
            p.iconst(12, 0)
            p.float_(14, 14, 12)                # F14 = e
            p.st(C["lg_e"], 14)
            p.iconst(13, 0x7FFFFF)
            p.iop(15, 15, "AND", 13)
            p.iconst(13, 0x3F800000)
            p.iop(15, 15, "OR", 13)             # m
            p.fconst(12, 1.0)
            p.fop(13, 15, "+", 12)              # m + 1
            p.fop(15, 15, "-", 12)              # m - 1
            p.st(C["lg_t"], 15)
            _recip_body(p, 13, 14, 15)          # F14 = recip(m + 1)
            p.ld(15, C["lg_t"])
            p.fop(15, 15, "*", 14)              # t
            p.fop(14, 15, "*", 15)              # t2
            _horner(p, 13, 14, [1.0, 1.0 / 3.0, 1.0 / 5.0, 1.0 / 7.0, 1.0 / 9.0])
            p.fop(15, 15, "*", 13)
            p.fconst(12, float(LV.INV_LN2_2))
            p.fop(15, 12, "*", 15)
            p.ld(14, C["lg_e"])
            p.fop(15, 14, "+", 15)
        p.fconst(12, 0.0)
        p.if_(15, "LE", 12, lambda: p.fconst(15, -126.0), rest)
    _leaf(p, "s_log2", body)


SLEAF = {"s_log2": _s_log2,
         "sb1": _xs_leaf("sb1", 2, VOICE["rs1"], "bi"),
         "sb2": _xs_leaf("sb2", 2, VOICE["rs2"], "bi")}


def log2f(x) -> E:
    return Fn("s_log2", x)


def ex(x) -> E:
    return exp2(w(x) * k(1.44269504088896))


def sinf(x) -> E:
    return OP.sinf(x)


def cosf(x) -> E:
    return OP.sinf(w(x) + k(1.57079633))


def bi1() -> E:
    return Fn("sb1", Kc(0.0))


def bi2() -> E:
    return Fn("sb2", Kc(0.0))


def u1() -> E:
    return bi1() * k(0.5) + k(0.5)


def u2() -> E:
    return bi2() * k(0.5) + k(0.5)


def clipe(x, lo, hi) -> E:
    return mn(mx(x, k(lo)), k(hi))


class SG(OP.OG):
    """FASCIA's compiler with ORGAN's leaves and SILT's"""

    def call_at(self, name: str, r: int) -> None:
        if name not in SLEAF:
            return super().call_at(name, r)
        p = self.p
        if r == 0:
            SLEAF[name](self)
            return
        p.fpass(r + 1, 0)
        p.fpass(0, r)
        SLEAF[name](self)
        p.fpass(r, 0)
        p.fpass(0, r + 1)

    def V(self, name, j: int = 0) -> Mv:
        return Mv("i", 2, VOICE[name] + j)

    def Pk(self, name) -> Mv:
        """player k's word (I3 = the voice + 4 k)"""
        return Mv("i", 3, VOICE[name])

    def a(self, arr, j) -> Mv:
        return Mv("a", self.L.A[arr] + 4 * j)

    def ivloop(self, cnt: str, body) -> None:
        FP_.FP.ivloop(self, cnt, body)

    def tabw(self, d: int, name: str, idx_word: str) -> None:
        """Rd = TABLE name[the int word idx_word]"""
        p = self.p
        p.ld(12, self.L.C[idx_word])
        p.lsh(12, 12, 2)
        p.iconst(13, self.L.tables + 4 * TAB[name][0])
        p.iop(12, 13, "+", 12)
        p.seti(1, 12)
        p.ldi(d, 0, 1)

    def ifint(self, word_mv: Mv, cond: str, v: int, then, else_=None) -> None:
        self.icmp(word_mv, cond, v, then, else_)

    def crv(self, dst: str, x: E, shape_word: Mv) -> None:
        """c(dst) = live.crv(x, shape)"""
        c, p = self.c, self.p
        self.set(c("cx"), x)

        def inside():
            def soft():
                self.set(c(dst), (c("cx") * c("cx")) * (k(3.0) - k(2.0) * c("cx")))

            def other():
                self.icmp(shape_word, "EQ", 2, lambda: self.powf(dst, c("cx"), k(2.5)),
                          lambda: self.set(c(dst), c("cx")))
            self.icmp(shape_word, "EQ", 0, soft, other)

        def above():
            self.cmp(c("cx"), "GE", k(1.0), lambda: self.set(c(dst), k(1.0)), inside)
        self.cmp(c("cx"), "LE", k(0.0), lambda: self.fz(c(dst)), above)

    def powf(self, dst: str, x: E, y: E) -> None:
        """c(dst) = live.powf(x, y)"""
        c = self.c
        self.set(c("px"), x)
        self.cmp(c("px"), "LE", k(0.0), lambda: self.fz(c(dst)),
                 lambda: self.set(c(dst), exp2(w(y) * log2f(c("px")))))

    def floorw(self, m: Mv) -> None:
        """m = m - floor(m) (live: v - F(np.floor(v)))"""
        p = self.p
        self.ld(0, m)
        p.fpass(15, 0)
        OP._floor_f(p, 15, 14)
        p.fop(0, 0, "-", 14)
        self.st(m, 0)

    def floor_of(self, dst: Mv, x: E) -> None:
        """dst = floor(x) (a float)"""
        p = self.p
        self.ev(w(x), 0)
        p.fpass(15, 0)
        OP._floor_f(p, 15, 14)
        p.fpass(0, 14)
        self.st(dst, 0)

    def trunc_to(self, dst: str, x: E) -> None:
        """the int word dst = int(x) (TRUNC)"""
        p = self.p
        self.ev(w(x), 0)
        p.trunc(0, 0)
        p.st(self.L.C[dst], 0)

    def wander(self, kk: E, slot_word: str, slot: int, rng: str, x01=None) -> None:
        """live.wander on the voice words slot_word[slot], [slot + 1] with noise rng (or on X01)"""
        c = self.c
        if x01 is None:
            x0 = Mv("i", 2, VOICE[slot_word] + slot)
            x1 = Mv("i", 2, VOICE[slot_word] + slot + 1)
        else:
            x0, x1 = x01
        dt = k(LV.DT)
        self.set(c("wk"), w(kk))
        self.set(c("wa"), mn(k(1.0), (c("wk") * dt) * k(2.0)))
        b = bi1() if rng == "1" else bi2()
        self.set(x1, x1 + (b * k(1.7) - x1) * c("wa"))
        self.set(x0, x0 + (x1 - x0) * mn(k(1.0), c("wk") * dt))

    def bow_k(self, dst: str, dv: E, slope: E, offset: E) -> None:
        c = self.c
        self.set(c("bt"), ab(w(dv) * w(slope)) + w(offset))
        self.set(c("b2"), c("bt") * c("bt"))
        self.set(c("b4"), c("b2") * c("b2"))
        self.cmp(c("b4"), "LE", k(1.0), lambda: self.set(c(dst), k(1.0)),
                 lambda: self.set(c(dst), recip(c("b4"))))

    # -- the slot's lines (DDR) -------------------------------------------------------------------
    def line_base(self) -> None:
        """c('lnb') = SILT_DELAY_DDR + 0xC000 t (an int word)"""
        p, L = self.p, self.L
        p.ld(9, L.t_word)
        p.iconst(12, 0xC000)
        p.mul_ssi(12, 9, 12)
        p.iconst(13, L.lines)
        p.iop(12, 13, "+", 12)
        p.st(L.C["lnb"], 12)

    def rd(self, dst: str, line_off: int, n: int, wptr: Mv, d: E) -> None:
        """c(dst) = live.rd(line, n, w, d): the line at word line_off of the slot's lines"""
        p, c, C = self.p, self.c, self.L.C
        self.set(c("rdd"), w(d))
        self.ld(0, c("rdd"))
        p.trunc(1, 0)                           # di
        p.iconst(12, 0)
        p.float_(2, 1, 12)
        p.fop(0, 0, "-", 2)
        p.st(C["rfr"], 0)                       # fr = d - di
        self.ld(9, wptr)
        p.iop(9, 9, "-", 1)                     # r0 = w - di
        p.iconst(12, n)
        p.ifz(9, "LT", lambda: p.iop(9, 12, "+", 9))
        p.iconst(13, 1)
        p.iop(10, 9, "-", 13)                   # r1 = r0 - 1
        p.ifz(10, "LT", lambda: (p.iconst(12, n), p.iop(10, 12, "+", 10)))
        p.ld(11, C["lnb"])
        p.iconst(12, 4 * line_off)
        p.iop(11, 12, "+", 11)
        p.lsh(12, 9, 2)
        p.iop(12, 12, "+", 11)
        p.seti(1, 12)
        p.ldi(3, 0, 1)                          # buf[r0]
        p.lsh(12, 10, 2)
        p.iop(12, 12, "+", 11)
        p.seti(1, 12)
        p.ldi(4, 0, 1)                          # buf[r1]
        p.fop(4, 4, "-", 3)
        p.ld(5, C["rfr"])
        p.fop(4, 4, "*", 5)
        p.fop(3, 3, "+", 4)
        p.st(C[dst], 3)

    def wr(self, line_off: int, idx: Mv, val: E) -> None:
        """the line's word idx = val"""
        p, C = self.p, self.L.C
        self.ev(w(val), 0)
        self.ld(9, idx)
        p.ld(11, C["lnb"])
        p.iconst(12, 4 * line_off)
        p.iop(11, 12, "+", 11)
        p.lsh(12, 9, 2)
        p.iop(12, 12, "+", 11)
        p.seti(1, 12)
        p.sti(0, 1, 0)

    def bump_ptr(self, m: Mv, n: int) -> None:
        """m = m + 1 if m + 1 < n else 0 (an int word)"""
        p = self.p
        self.ld(9, m)
        p.iconst(12, 1)
        p.iop(9, 12, "+", 9)
        p.iconst(12, n)
        p.if_(9, "GE", 12, lambda: p.iconst(9, 0), kind="i")
        self.st(m, 9)

    # -- a block of the slot --------------------------------------------------------------------
    def voice(self, t: int | None) -> None:
        p, C, L = self.p, self.L.C, self.L
        V, c = self.V, self.c
        if p.run:
            p.iconst(9, t)
            p.st(L.t_word, 9)
        self.vbase()
        self.line_base()
        self.read_note()
        # the note-off: mask 36, bit t
        p.ld(0, OFF_WORD)
        p.iconst(1, 1)
        p.ld(9, L.t_word)
        PP._shift_by(p, 1, 9)
        p.iop(0, 0, "AND", 1)
        p.st(C["off"], 0)
        self.read_knobs()
        # a state this program did not write (power-on, or the walk's type change): a fresh voice,
        # its lines clearing (live.SlotVoice())
        self.ld(0, V("magic"))
        p.iconst(1, MAGIC)
        p.if_(0, "NE", 1, self.fresh, kind="i")
        self.stolen_check()

        def note_on():
            self.new_note()
            p.ld(9, L.t_word)
            p.iop(10, 9, "+", 9)
            PP.half(p, 4, FP_.VEL_OFFSET, 10)
            p.lsh(4, 4, -8)
            p.iconst(12, 127)
            p.iop(4, 4, "MIN", 12)
            p.iconst(12, 0)
            p.float_(4, 4, 12)
            p.fconst(5, float(LV.INV127))
            p.fop(4, 4, "*", 5)
            p.st(C["tvel"], 4)
            self.note()
        p.ld(0, C["trig"])
        p.ifz(0, "NE", note_on)
        self.block()
        self.ld(0, V("rest"))
        p.iconst(1, 1)
        p.iop(0, 1, "-", 0)
        self.st(V("on"), 0)                     # FASCIA's life word: sounding

    def vbase(self) -> None:
        """I2 = the slot's state (ORGAN's), and its address in c('vba')"""
        OP.OG.vbase(self)
        self.p.st(self.L.C["vba"], 12)

    def stolen_check(self) -> None:
        """the guard left this voice out twice in one note (perc.guard.around): it rests"""
        p = self.p
        self._slot_word(self.L.stolen)
        p.ldi(0, 0, 1)

        def rest():
            p.iconst(0, 0)
            p.sti(0, 1, 0)
            self.iset(self.V("rest"), 1)
        p.ifz(0, "NE", rest)

    def fresh(self) -> None:
        """live.Voice(seed) then become(): every word zero, the seeds, the lines clearing"""
        p, L = self.p, self.L
        V = self.V
        p.iconst(0, 0)
        for j in range(VOICE_WORDS):
            p.sti(j, 2, 0)
        p.fconst(0, 1.0)
        self.st(V("loop_per"), 0)
        self.st(V("vel"), 0)
        p.fconst(0, 110.0)
        self.st(V("f0"), 0)
        p.iconst(0, 1)
        self.st(V("rest"), 0)
        # rs1 = (0x2545f491 + t) | 1, rs2 = (rs1 7) | 1 (live: Rng(seed), Rng(seed 7))
        p.ld(9, L.t_word)
        p.iconst(12, 0x2545F491)
        p.iop(0, 12, "+", 9)
        p.iconst(12, 1)
        p.iop(0, 0, "OR", 12)
        self.st(V("rs1"), 0)
        p.iconst(12, 7)
        p.mul_ssi(1, 0, 12)
        p.iconst(12, 1)
        p.iop(1, 1, "OR", 12)
        self.st(V("rs2"), 1)
        p.iconst(0, MAGIC)
        self.st(V("magic"), 0)

    def read_knobs(self) -> None:
        """the 32 knobs from FASCIA's records' frame words (organ.live.knob_of), pages 1-3 as they
        are, page 4 as options ((k N) >> 7, at most N - 1): live.eff_of"""
        from ..fascia import machines as FM
        from ..organ import live as OL
        p, C, L = self.p, self.L.C, self.L
        p.ld(9, L.t_word)
        PP.t146(p, 10, 9)
        p.st(C["k146"], 10)
        for j, ride in enumerate(OL.RIDES):
            _rid, slot, lo, top = FM.SLOTS[ride]
            assert lo == 0
            p.ld(10, C["k146"])
            PP.half(p, 4, 168 + 2 * slot, 10)
            p.lsh(4, 4, -8)
            p.iconst(12, top)
            p.iop(4, 4, "MIN", 12)
            if top != 127:
                p.iconst(12, 0)
                p.float_(4, 4, 12)
                p.fconst(6, 254.0 / (200 if top == 100 else 240))
                p.fop(4, 4, "*", 6)
                p.fconst(6, 0.502)
                p.fop(4, 4, "+", 6)
                p.trunc(4, 4)
            if j >= 24:
                n = len(LV.CHOICES[LV.CONTROLS[j]])
                p.iconst(12, n)
                p.mul_ssi(4, 4, 12)
                p.lsh(4, 4, -7)
                p.iconst(12, n - 1)
                p.iop(4, 4, "MIN", 12)
            p.iconst(12, 0)
            p.float_(4, 4, 12)
            p.st(C[f"e{j}"], 4)

    # -- live.Voice.note ---------------------------------------------------------------------------
    def note(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c

        def wait():
            self.set(V("wnote"), c("nn"))
            self.set(V("wvel"), c("tvel"))
            self.iset(V("wait"), 1)
            self.iset(V("woff"), 0)

        def maybe():
            def other_mat():
                self.iset(V("fadef"), 1)
                wait()

            def check_mat():
                self.ld(0, V("L4"))
                p.iconst(12, 0)
                p.float_(0, 0, 12)
                self.ld(1, c("e24"))
                p.if_(0, "NE", 1, other_mat, lambda: self.strike(c("nn"), c("tvel")))
            self.icmp(V("rest"), "EQ", 0, check_mat, lambda: self.strike(c("nn"), c("tvel")))

        def clearing_or_fading():
            self.icmp(V("fadef"), "NE", 0, wait, maybe)
        self.ld(0, V("clear_at"))
        p.iconst(1, LV.LINE_WORDS)
        p.if_(0, "LT", 1, wait, clearing_or_fading, kind="i")

    def strike(self, note: Mv, vel: Mv) -> None:
        """live.Voice.note past its waiting tests: the gesture starts again"""
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        self.set(c("tmp0"), note)
        self.set(c("tmp1"), vel)
        self.set(V("f0"), k(440.0) * exp2((c("tmp0") - k(69.0)) * k(1.0 / 12.0)))
        self.set(V("vel"), c("tmp1"))
        self.iset(V("gate"), 1)
        self.iset(V("rest"), 0)
        self.fz(V("t_note"))
        self.set(V("strike"), k(1.0))
        self.fz(V("burst"))
        self.fz(V("vib_env"))
        self.fz(V("gl_amt"))
        for j in range(8):
            self.ld(0, c(f"e{24 + j}"))
            p.trunc(0, 0)
            self.st(V("L4", j), 0)
        self.set(c("spread"), c("e16"))
        for kk in range(LV.NSEC):
            self.set(c("u"), bi1())
            dist = V("L4", 3)

            def d0():
                self.set(c("cl"), c("u") * k(0.5))

            def d1():
                self.set(c("cl"), c("u"))

            def d2(kk=kk):
                self.set(c("cl"), (k(0.6) + k(0.4) * ab(c("u"))) * k(LV.ALTK[kk]))

            def d3():
                self.powf("cl", ab(c("u")), k(0.7))
            self.icmp(dist, "EQ", 0, d0, lambda: self.icmp(dist, "EQ", 1, d1,
                                                           lambda: self.icmp(dist, "EQ", 2, d2, d3)))
            self.set(c("cents"), c("cl") * (k(5.0) + c("spread") * k(195.0 / 127.0)))
            tune = V("L4", 6)

            def t1():
                def snap():
                    self.floor_of(c("cents"), c("cents") * k(0.01) + k(0.5))
                    self.set(c("cents"), c("cents") * k(100.0))
                self.cmp(c("spread"), "GT", k(70.0), snap)

            def t2():
                self.floor_of(c("cents"), c("cents") * k(0.02) + k(0.5))
                self.set(c("cents"), c("cents") * k(50.0))

            def t3(kk=kk):
                self.set(c("cents"), c("cents") * k(0.2) + k(LV.HARM[kk]) * mn(k(1.0), c("spread") * k(1.0 / 64.0)))
            self.icmp(tune, "EQ", 1, t1, lambda: self.icmp(tune, "EQ", 2, t2,
                                                           lambda: self.icmp(tune, "EQ", 3, t3)))
            self.set(V("soff", kk), c("cents"))
            self.fz(V("sbow", kk))
            self.set(V("sdel", kk), ((k(0.002) + (c("e22") * k(LV.INV127)) * k(0.035))
                                     + (k(1.0) - c("e3") * k(LV.INV127)) * k(0.02)) * u2())
            self.ev(V("sdel", kk) * k(48000.0), 0)
            p.trunc(0, 0)
            p.iconst(12, 0)
            p.iop(0, 12, "-", 0)
            self.st(V("scnt", kk), 0)
        # simp: LEGNO, FRACT, or SKIN's STACC and SPICC
        g_, m_ = V("L4", 1), V("L4", 0)

        def simp_on():
            self.set(V("simp"), k(0.6) + k(0.4) * V("vel"))

        def skin_g():
            self.icmp(g_, "EQ", 2, simp_on, lambda: self.icmp(g_, "EQ", 4, simp_on, lambda: self.fz(V("simp"))))
        self.icmp(g_, "EQ", 5, simp_on, lambda: self.icmp(g_, "EQ", 7, simp_on,
                                                          lambda: self.icmp(m_, "EQ", 2, skin_g, lambda: self.fz(V("simp")))))
        self.fz(V("loop_t"))
        self.set(V("loop_per"), (k(0.04) + (k(1.0) - c("e9") * k(LV.INV127)) * k(0.5))
                 * (k(1.0) + (c("e12") + c("e22")) * k(0.8 / 254.0) * bi2()))

    # -- live.Voice.block --------------------------------------------------------------------------
    def block(self) -> None:
        p, C, L = self.p, self.L.C, self.L
        V, c = self.V, self.c

        def offk():
            self.icmp(V("wait"), "NE", 0, lambda: self.iset(V("woff"), 1), lambda: self.iset(V("gate"), 0))
        p.ld(0, C["off"])
        p.ifz(0, "NE", offk)
        self.iset(c("fadeo"), 0)

        def fade_blk():
            self.iset(V("fadef"), 0)
            self.iset(c("fadeo"), 1)
            self.rt("s_render", self.render)
            self.iset(V("rest"), 1)
            self.iset(V("clear_at"), 0)          # become()

        def not_fading():
            def clearing():
                self.clear_step()
                self.zeros()

            def ready():
                def apply_wait():
                    self.iset(V("wait"), 0)
                    self.strike_waiting()
                    self.icmp(V("woff"), "NE", 0, lambda: self.iset(V("gate"), 0))
                self.icmp(V("wait"), "NE", 0, apply_wait)
                self.icmp(V("rest"), "NE", 0, self.zeros, lambda: self.rt("s_render", self.render))
            self.ld(0, V("clear_at"))
            p.iconst(1, LV.LINE_WORDS)
            p.if_(0, "LT", 1, clearing, ready, kind="i")
        self.icmp(V("fadef"), "NE", 0, fade_blk, not_fading)

    def strike_waiting(self) -> None:
        """the waiting note: live.note(P, *waiting) strikes (the lines are clear, the fade is done
        and the voice rests: every way to a clear leaves it resting, so no material test)"""
        self.strike(self.V("wnote"), self.V("wvel"))

    def clear_step(self) -> None:
        """live.Voice._clear_step: 512 words of the lines from clear_at"""
        p, C = self.p, self.L.C
        V = self.V
        self.ld(9, V("clear_at"))
        p.lsh(12, 9, 2)
        p.ld(11, C["lnb"])
        p.iop(12, 11, "+", 12)
        p.seti(4, 12)
        p.fconst(5, 0.0)
        p.loop_r(10, LV.CLEAR_WORDS, lambda: p.stpost(4, 5), one=11)
        self.ld(9, V("clear_at"))
        p.iconst(12, LV.CLEAR_WORDS)
        p.iop(9, 12, "+", 9)
        self.st(V("clear_at"), 9)

    def zeros(self) -> None:
        OP.OG.zeros(self)

    # -- the render (live.Voice._render): its block part, then the samples ----------------------
    def render(self) -> None:
        self.blk_gesture()
        self.blk_pitch()
        self.blk_coefs()
        self.blk_materials()
        self.blk_players()
        self.samples()

    def blk_gesture(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        e = lambda j: c(f"e{j}")              # noqa: E731
        DT = k(LV.DT)
        I127 = k(LV.INV127)
        L4 = lambda j: V("L4", j)              # noqa: E731
        self.set(c("tn"), V("t_note") + DT)

        def looping():
            def per_beat():
                lk = L4(4)
                self.icmp(lk, "EQ", 1, lambda: self.set(c("lb"), k(0.25)),
                          lambda: self.icmp(lk, "EQ", 2, lambda: self.set(c("lb"), k(0.5)),
                                            lambda: self.set(c("lb"), k(1.0))))
                self.set(V("loop_per"), (k(60.0) * recip(k(120.0))) * c("lb"))
            self.icmp(L4(4), "LT", 4, per_beat)
            self.set(V("loop_t"), V("loop_t") + DT)

            def again():
                self.set(V("loop_t"), V("loop_t") - V("loop_per"))
                self.set(c("tn"), DT)
                self.set(V("strike"), k(1.0))
                for kk in range(LV.NSEC):
                    self.ev(V("sdel", kk) * k(48000.0), 0)
                    p.trunc(0, 0)
                    p.iconst(12, 0)
                    p.iop(0, 12, "-", 0)
                    self.st(V("scnt", kk), 0)

                def free():
                    self.set(V("loop_per"), (k(0.04) + (k(1.0) - e(9) * I127) * k(0.5))
                             * (k(1.0) + (e(12) + e(22)) * k(0.8 / 254.0) * bi2()))
                self.icmp(L4(4), "EQ", 4, free)
            self.cmp(V("loop_t"), "GE", V("loop_per"), again)

        def lk_on():
            self.cmp(c("tn"), "GT", DT, looping)
        self.icmp(V("gate"), "NE", 0, lambda: self.icmp(L4(4), "GT", 0, lk_on))
        self.set(V("t_note"), c("tn"))
        for j, nm in enumerate(KNOB_WORDS):
            self.set(c(nm), e(j) * I127)
        cohe = c("cohe")
        self.cmp(cohe, "GT", k(0.55), lambda: self.set(c("lock"), (cohe - k(0.55)) * k(1.0 / 0.45)),
                 lambda: self.fz(c("lock")))
        self.cmp(cohe, "LT", k(0.55), lambda: self.set(c("loose"), (k(0.55) - cohe) * k(1.0 / 0.55)),
                 lambda: self.fz(c("loose")))
        for nm in ("sadd", "tgt", "ppush", "imp", "noisy", "gn"):
            self.fz(self.c(nm))
        self.set(c("entry"), k(1.0))
        self.set(c("damp_x"), k(1.0))
        self.set(c("oms"), k(1.0) - c("snap"))
        shape = L4(5)
        self.icmp(shape, "EQ", 0, lambda: self.set(c("shk"), k(3.0)),
                  lambda: self.icmp(shape, "EQ", 2, lambda: self.set(c("shk"), k(0.3)),
                                    lambda: self.set(c("shk"), k(1.0))))
        self.set(c("atk"), (k(0.004) + (c("oms") * c("oms")) * k(0.6)) * c("shk"))
        self.set(c("spd"), (k(0.04) + c("speedk") * k(0.28)) * (k(0.6) + k(0.4) * V("vel")))
        self.set(c("stlen"), k(0.03) + c("grain") * k(0.25))
        tn = c("tn")
        # held = gate or t_note < 0.05 (an int word)
        self.iset(c("held"), 1)
        self.icmp(V("gate"), "EQ", 0, lambda: self.cmp(tn, "LT", k(0.05), None, lambda: self.iset(c("held"), 0)))
        held = lambda then, else_: self.icmp(c("held"), "NE", 0, then, else_)    # noqa: E731
        gest = L4(1)

        def g0():
            held(lambda: self.set(c("tgt"), c("spd")), lambda: self.fz(c("tgt")))

        def g1():
            self.wander(k(9.0), "wnd", 6, "1")
            held(lambda: self.set(c("tgt"), c("spd") * (k(0.7) + k(0.6) * V("wnd", 6))), lambda: self.fz(c("tgt")))
            self.set(c("ppush"), k(0.35) + k(0.2) * V("wnd", 6))
            self.set(c("noisy"), k(0.25))

        def g2():
            self.cmp(tn, "LT", c("stlen"), lambda: self.set(c("tgt"), c("spd") * k(1.3)), lambda: self.fz(c("tgt")))
            self.set(c("ppush"), k(0.15))
            self.cmp(tn, "GE", c("stlen"),
                     lambda: self.set(c("damp_x"), k(1.0) + k(6.0) * (k(1.0) - mn(k(1.0), (tn - c("stlen")) * k(1.0 / 0.08)))))

        def g3():
            self.set(c("rate"), k(6.0) + c("speedk") * k(14.0))
            self.set(c("ph"), tn * c("rate"))
            self.floorw(c("ph"))
            self.iset(c("hold3"), 1)
            self.icmp(V("gate"), "EQ", 0, lambda: self.cmp(tn, "LT", k(0.1), None, lambda: self.iset(c("hold3"), 0)))

            def on():
                self.cmp(c("ph"), "LT", k(0.5), lambda: self.set(c("tgt"), c("spd")),
                         lambda: self.set(c("tgt"), -c("spd")))
            self.icmp(c("hold3"), "NE", 0, on, lambda: self.fz(c("tgt")))

        def g4():
            self.iset(c("k_b"), 0)
            self.set(c("tt"), tn)
            self.set(c("per"), k(0.09) + (k(1.0) - c("speedk")) * k(0.12))
            self.set(c("amp_b"), k(1.0))
            self.iset(c("bdone"), 0)
            for _ in range(12):
                def step():
                    def go():
                        self.set(c("tt"), c("tt") - c("per"))
                        self.set(c("per"), c("per") * k(0.82))
                        p.ld(9, C["k_b"])
                        p.iconst(12, 1)
                        p.iop(9, 12, "+", 9)
                        p.st(C["k_b"], 9)
                        self.set(c("amp_b"), c("amp_b") * k(0.85))
                    self.cmp(c("tt"), "GT", c("per"), go, lambda: self.iset(c("bdone"), 1))
                self.icmp(c("bdone"), "EQ", 0, step)

            def on():
                self.set(c("tgt"), (c("spd") * k(1.4)) * c("amp_b"))

            def chk():
                self.cmp(c("tt"), "LT", c("stlen") * k(0.6), on, lambda: self.fz(c("tgt")))
            self.icmp(c("k_b"), "LT", 12, chk, lambda: self.fz(c("tgt")))

        def g5():
            self.set(c("imp"), V("strike") * (k(0.6) + k(0.4) * V("vel")))

        def g6():
            held(lambda: self.set(c("tgt"), c("spd")), lambda: self.fz(c("tgt")))
            self.set(c("gn"), clipe((e(20) - k(64.0)) * k(1.0 / 63.0), -1.0, 1.0))
            self.crv("cv", tn * recip(k(0.4) + (k(1.0) - c("speedk")) * k(3.0)), shape)
            self.set(V("gl_amt"), (c("gn") * k(12.0)) * c("cv"))

        def g8():
            self.crv("ramp", tn * recip(k(0.3) + (k(1.0) - c("speedk")) * k(4.0)), shape)
            held(lambda: self.set(c("tgt"), c("spd") * (k(0.15) + k(0.85) * c("ramp"))), lambda: self.fz(c("tgt")))
            self.set(c("ppush"), k(0.3) * c("ramp"))
            self.set(c("sadd"), k(0.35) * c("ramp"))
            self.set(c("entry"), c("ramp"))

        def g9():
            self.crv("ramp", tn * recip(k(0.5) + (k(1.0) - c("speedk")) * k(4.0)), shape)
            self.set(V("qph"), V("qph") + (k(3.0) + k(17.0) * c("ramp")) * DT)
            self.floorw(V("qph"))
            self.wander(k(6.0) + k(20.0) * c("ramp"), "wnd", 10, "1")
            held(lambda: self.set(c("tgt"), c("spd") * (k(1.0) + (k(0.5) * c("ramp")) * sinf(k(LV.TWO_PI) * V("qph")))),
                 lambda: self.fz(c("tgt")))
            self.set(c("ppush"), (k(0.3) * c("ramp")) * (k(0.5) + k(0.5) * V("wnd", 10)))
            self.set(c("sadd"), k(0.7) * c("ramp"))

        def g7():
            self.set(c("imp"), V("strike"))

            def maybe():
                def add():
                    self.set(c("imp"), c("imp") + (k(0.5) * u1()) * (k(1.0) - mn(k(1.0), tn * k(1.5))))
                self.cmp(u1(), "LT", (k(0.15) + c("dens") * k(0.8)) * (k(1.0) - tn), add)
            self.cmp(tn, "LT", k(0.05) + c("grain") * k(0.8), maybe)
        gs = {0: g0, 1: g1, 2: g2, 3: g3, 4: g4, 5: g5, 6: g6, 8: g8, 9: g9}

        def chain(keys):
            if not keys:
                return g7()
            kk = keys[0]
            self.icmp(gest, "EQ", kk, gs[kk], lambda: chain(keys[1:]))
        chain([0, 1, 2, 3, 4, 5, 6, 8, 9])
        self.icmp(gest, "EQ", 7, lambda: self.set(c("imp_sub"), c("imp") - V("strike")), lambda: self.fz(c("imp_sub")))
        self.fz(V("strike"))

        def scoop():
            self.set(c("gn"), clipe((e(20) - k(64.0)) * k(1.0 / 63.0), -1.0, 1.0))
            self.crv("cv", tn * recip(k(0.03) + (k(1.0) - c("speedk")) * k(0.6)), shape)
            self.set(V("gl_amt"), (c("gn") * k(12.0)) * (k(1.0) - c("cv")))
        self.icmp(gest, "NE", 6, lambda: self.cmp(ab(e(20) - k(64.0)), "GT", k(0.5), scoop))

        def unsteady():
            self.wander(k(2.5), "wnd", 12, "2")
            self.set(c("tgt"), c("tgt") * (k(1.0) + (c("loose") * k(0.45)) * V("wnd", 12)))
        self.cmp(c("loose"), "GT", k(0.0), lambda: self.cmp(c("tgt"), "NE", k(0.0), unsteady))
        self.icmp(shape, "EQ", 2, lambda: self.cmp(tn, "LT", k(0.15),
                                                   lambda: self.set(c("ppush"), c("ppush") + k(0.3) * ex(-tn * k(20.0)))))
        self.set(c("stress"), mn(k(1.0), (((((k(0.45) * c("press")) * c("press") + (k(0.25) * c("rosin")) * c("inst"))
                                             + (k(0.5) * c("inst")) * c("inst")) + k(0.3) * c("rough"))
                                           + k(0.25) * c("scrap")) + c("sadd")))
        self.cmp(c("stress"), "GT", k(0.6),
                 lambda: self.set(c("stress"), k(0.6) + k(0.25) * tanh((c("stress") - k(0.6)) * k(4.0))))
        # MORPH on a struck gesture: the hit splinters
        morph = c("morph")

        def splinter():
            self.set(c("imp"), c("imp") + (morph * k(0.5)) * u2())

        def m_test():
            self.cmp(c("tgt"), "EQ", k(0.0), lambda: self.cmp(tn, "LT", k(0.05) + k(0.6) * morph,
                     lambda: self.cmp(u2(), "LT", morph * (k(0.1) + c("dens") * k(0.6)), splinter)))

        def struck():
            self.icmp(gest, "EQ", 2, m_test, lambda: self.icmp(gest, "EQ", 4, m_test,
                      lambda: self.icmp(gest, "EQ", 5, m_test, lambda: self.icmp(gest, "EQ", 7, m_test))))
        self.cmp(morph, "GT", k(0.01), struck)
        mat = L4(0)

        def flutter():
            self.set(c("imp"), c("imp") + k(0.25) * (k(0.4) + k(0.6) * u2()))

        def skin_dens():
            self.cmp(e(6), "GT", k(32.0), lambda: self.cmp(tn, "LT", k(0.05) + c("grain") * k(0.4),
                     lambda: self.cmp(u2(), "LT", (e(6) - k(32.0)) * k(0.25 / 95.0), flutter)))
        self.icmp(mat, "EQ", 2, skin_dens)

        def pulse():
            self.ev((k(0.00015) + (c("oms") * c("oms")) * k(0.004)) * k(48000.0), 0)
            p.trunc(0, 0)
            p.iconst(12, 4)
            p.iop(0, 0, "MAX", 12)
            self.st(V("p_n"), 0)
            self.iset(V("p_i"), 0)
            self.set(V("p_a"), c("imp"))
        self.cmp(c("imp"), "GT", k(0.0), pulse)

        def skin_snap():
            self.ev((k(0.0002) + (c("oms") * c("oms")) * k(0.003)) * k(48000.0), 0)
            p.trunc(0, 0)
            p.iconst(12, 4)
            p.iop(0, 0, "MAX", 12)
            self.st(V("p_n"), 0)
            self.iset(V("p_i"), 0)
            self.set(V("p_a"), k(0.3) + k(0.5) * c("snap"))

        def sk_g():
            self.icmp(gest, "EQ", 2, skin_snap, lambda: self.icmp(gest, "EQ", 3, skin_snap,
                                                                  lambda: self.icmp(gest, "EQ", 4, skin_snap)))
        self.icmp(mat, "EQ", 2, lambda: self.cmp(c("tgt"), "NE", k(0.0),
                                                 lambda: self.cmp(V("prev_tgt"), "EQ", k(0.0), sk_g)))
        self.set(V("prev_tgt"), c("tgt"))

        def chaotic():
            self.wander(k(5.0), "wnd", 8, "1")
            self.set(c("tgt"), c("tgt") * (k(1.0) + k(0.5) * V("wnd", 8)))
        self.icmp(shape, "EQ", 3, chaotic)

        def fragments():
            self.set(V("part_t"), V("part_t") - DT)
            self.set(c("pmin"), k(0.002) + (k(1.0) - c("dens")) * k(0.08))

            def new_frag():
                self.set(V("part_t"), c("pmin") * (k(0.5) + u1()))
                self.cmp(u1(), "LT", k(0.3) + k(0.7) * c("cohe"), lambda: self.set(V("burst"), k(1.0)),
                         lambda: self.set(V("burst"), k(0.3)))
                self.set(V("mo_c"), ((morph * morph) * k(350.0)) * bi2())
            self.cmp(V("part_t"), "LE", k(0.0), new_frag)
            self.cmp(V("part_t"), "GT", c("pmin") * k(0.6), lambda: self.set(c("two"), k(2.0)), lambda: self.fz(c("two")))
            self.set(c("tgt"), c("tgt") * (k(1.0) - morph) + ((c("tgt") * morph) * V("burst")) * c("two"))
        self.cmp(morph, "GT", k(0.01), lambda: self.cmp(c("tgt"), "NE", k(0.0), fragments))

    def blk_pitch(self) -> None:
        p = self.p
        V, c = self.V, self.c
        DT = k(LV.DT)
        self.set(V("vib_env"), mn(k(1.0), V("vib_env") + DT * k(1.0 / 0.6)))
        self.set(V("vib_ph"), V("vib_ph") + (k(4.5) + k(2.0) * c("inst")) * DT)
        self.floorw(V("vib_ph"))
        self.wander(k(0.6), "wnd", 0, "1")
        self.wander(k(11.0), "wnd", 2, "1")
        self.wander(k(7.0), "wnd", 4, "1")
        self.set(c("vib_s"), sinf(k(LV.TWO_PI) * V("vib_ph")))
        self.set(c("cents"), ((c("vibr") * k(45.0)) * V("vib_env")) * c("vib_s") + (c("drift") * k(25.0)) * V("wnd", 0)
                 + ((c("stress") * c("stress")) * k(25.0)) * V("wnd", 2))
        self.icmp(V("L4", 3), "NE", 3, lambda: self.set(c("glp"), V("gl_amt") * k(100.0)), lambda: self.fz(c("glp")))
        self.set(c("cents"), c("cents") + c("glp"))
        self.cmp(c("morph"), "GT", k(0.01), lambda: self.set(c("cents"), c("cents") + V("mo_c")))
        self.icmp(V("L4", 0), "EQ", 2, lambda: self.fz(c("ak")), lambda: self.set(c("ak"), k(0.25)))
        self.set(c("alpha"), ((k(0.15) + k(0.6) * c("press")) * c("snap")) * c("ak"))
        self.set(c("tau"), k(0.01) + c("mass") * k(0.12))
        self.set(c("ov"), k(1200.0) * log2f(k(1.0) + c("alpha") * ex(-c("tn") * recip(c("tau")))))
        self.set(c("cents"), c("cents") + c("ov"))
        self.set(V("sq"), V("sq") * k(0.6703200460))

        def squeal():
            self.set(V("sq"), k(0.6) + k(0.4) * c("stress"))

        def sq_t():
            self.cmp(c("stress"), "GT", k(0.35), lambda: self.cmp(c("tgt"), "NE", k(0.0), lambda: self.cmp(
                u1(), "LT", (((c("stress") * c("stress")) * c("stress")) * DT) * k(6.0), squeal)))
        self.icmp(V("L4", 0), "EQ", 0, sq_t)
        self.set(c("f"), V("f0") * exp2(c("cents") * k(1.0 / 1200.0)))

    def blk_coefs(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        e = lambda j: c(f"e{j}")              # noqa: E731
        FS = k(48000.0)
        IFS = k(1.0 / 48000.0)
        NB4 = float(LV.NBR - 4)
        self.set(c("per"), FS * recip(mx(c("f"), k(25.0))))
        self.set(c("lpc"), ((k(0.32) + (k(0.55) * (k(1.0) - c("visc") * k(0.8))) * (k(0.55) + k(0.45) * c("tens")))
                            * (k(1.0) - k(0.3) * c("mass"))))
        self.cmp(c("damp_x"), "NE", k(1.0), lambda: self.set(c("lpc"), c("lpc") * recip(sqrt(c("damp_x")))))
        self.set(c("lpc"), clipe(c("lpc"), 0.08, 0.95))
        self.set(c("lpd"), (k(1.0) - c("lpc")) * recip(c("lpc")))
        self.set(c("tot"), mn(c("per") - c("lpd"), k(NB4)))
        self.set(c("beta"), k(0.04) + c("pos") * k(0.4))
        self.set(c("db"), clipe(c("tot") * c("beta"), 1.5, NB4))
        self.set(c("dn"), clipe(c("tot") - c("db"), 1.5, NB4))
        self.set(c("half"), clipe(c("db") + c("per") * k(0.5), 2.0, NB4))
        self.set(c("a_hp"), recip(k(1.0) + ((k(LV.TWO_PI) * k(0.45)) * c("f")) * IFS))
        self.cmp(c("morph"), "GT", k(0.0), lambda: self.set(c("lossm"), k(0.995) - (k(0.4) * c("morph")) * c("morph")),
                 lambda: self.set(c("lossm"), k(0.995)))
        self.cmp(e(0), "GT", k(42.0), lambda: self.set(c("stiff"), (e(0) - k(42.0)) * k(1.0 / 85.0)),
                 lambda: self.fz(c("stiff")))
        self.set(c("fapc"), k(-0.9) * c("stiff"))

        def stiff_on():
            self.set(c("fad"), (k(1.0) - c("fapc")) * recip(k(1.0) + c("fapc")))

            def cap():
                self.set(c("fad"), c("tot") * k(0.25))
                self.set(c("fapc"), (k(1.0) - c("fad")) * recip(k(1.0) + c("fad")))
            self.cmp(c("fad"), "GT", c("tot") * k(0.25), cap)
            self.set(c("db"), clipe(c("db") - c("fad"), 1.5, NB4))
        self.cmp(c("stiff"), "GT", k(0.0), stiff_on)

        def coarse():
            self.set(c("gg"), (e(5) - k(55.0)) * k(1.0 / 72.0))
            self.ev((c("gg") * c("gg")) * k(60.0), 0)
            p.trunc(0, 0)
            p.iconst(12, 1)
            p.iop(0, 12, "+", 0)
            p.st(C["ghold"], 0)
        self.cmp(e(5), "GT", k(55.0), coarse, lambda: self.iset(c("ghold"), 1))
        self.cmp(e(6), "GT", k(32.0), lambda: self.set(c("crk"), (e(6) - k(32.0)) * k(1.0 / 95.0)),
                 lambda: self.fz(c("crk")))
        self.set(c("pr"), mn(k(1.0), (c("press") * k(0.85) + c("ppush")) + (k(0.3) * c("stress")) * V("wnd", 4)))
        self.set(c("slope"), k(5.5) - c("pr") * k(4.2))
        self.set(c("offset"), k(0.92) - c("rosin") * k(0.3))
        self.cmp(c("pr"), "GT", k(0.7), lambda: self.set(c("breakup"), (c("pr") - k(0.7)) * k(1.6)),
                 lambda: self.fz(c("breakup")))
        self.set(c("att"), k(1.0) - ex(-recip(c("atk") * FS)))
        self.set(c("rel"), k(0.000694203))
        self.set(c("scr"), mn(k(1.0), (k(0.5) * c("scrap") + c("noisy")) + c("stress") * k(0.15)))
        self.cmp(c("scr"), "GT", k(0.3), lambda: self.set(c("scr"), k(0.3) + (c("scr") - k(0.3)) * k(0.5)))
        self.set(c("fs_b"), exp2(-c("mass") * k(1.9)))
        self.set(c("rr"), ex(-recip((k(0.02) + k(0.03) * (k(1.0) - c("visc"))) * FS)))
        for kk in range(4):
            self.set(c("wk_"), ((k(LV.TWO_PI) * k(LV.BFR[kk])) * c("fs_b")) * IFS)
            self.set(self.a("bc", kk), c("rr") * cosf(c("wk_")))
            self.set(self.a("bs", kk), c("rr") * sinf(c("wk_")))
        self.set(c("fcen"), k(300.0) * exp2(c("form") * k(4.5) + (V("env_e") * k(2.0)) * c("form")))
        self.set(c("tf"), (k(LV.PI) * mn(c("fcen"), k(16000.0))) * IFS)
        self.tanf("g_f", "tf")
        self.set(c("fa1"), recip(k(1.0) + c("g_f") * (c("g_f") + k(1.0 / 3.0))))
        self.set(c("fa2"), c("g_f") * c("fa1"))
        self.set(c("fa3"), c("g_f") * c("fa2"))
        self.ev(k(4.0) * c("voices") + k(0.5), 0)
        p.trunc(0, 0)
        p.iconst(12, 2)
        p.iop(0, 12, "+", 0)
        p.st(C["nm"], 0)

    def blk_materials(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        FS = k(48000.0)
        IFS = k(1.0 / 48000.0)
        NB4 = float(LV.NBR - 4)
        mat = V("L4", 0)
        shape = V("L4", 5)

        def silt():
            self.set(c("ppart"), k(1.0) + c("part"))
            for kk in range(6):
                self.powf("mr", k(LV.MEM[kk]) + (k(kk + 1) - k(LV.MEM[kk])) * c("tens"), c("ppart"))
                self.set(c("fk"), (c("f") * c("mr")) * (k(1.0) + ((c("inst") * k(0.02)) * V("env_e")) * k(kk + 1)))
                self.set(c("fk"), c("fk") * exp2((V("soff", kk) * c("spread")) * k(3.0 / 1200.0)))
                self.set(c("fk"), mn(c("fk"), k(20000.0)))
                self.set(c("dec"), ((k(0.04) + (k(1.0) - c("visc")) * k(0.9)) * (k(1.0) + c("mass")))
                         * recip((k(1.0) + k(0.6) * k(kk)) * c("damp_x")))
                self.set(c("dec"), c("dec") * (k(1.0) - k(0.85) * c("morph")))
                self.set(c("r"), ex(-recip(c("dec") * FS)))
                self.set(self.a("mc", kk), c("r") * cosf((k(LV.TWO_PI) * c("fk")) * IFS))
                self.set(self.a("ms", kk), c("r") * sinf((k(LV.TWO_PI) * c("fk")) * IFS))
        self.icmp(mat, "EQ", 1, silt)

        def skin():
            self.set(c("el"), (k(0.03) + (k(1.0) - c("tens")) * k(0.15)) + c("press") * k(0.08))
            skE = V("sk_E")
            self.set(c("sk_cut"), mn(k(16000.0), ((c("f") * ((k(1.0) + k(3.0) * c("tens")) + (k(30.0) * skE) * (k(0.3) + c("press"))))
                                                  + (k(2500.0) * c("snap")) * skE) * (k(1.0) - k(0.4) * c("visc"))))
            self.set(c("cut_l"), mn(k(18000.0), (((c("f") * (k(3.0) + k(25.0) * c("tens"))) * (k(1.0) + k(0.5) * skE))
                                                 * (k(1.0) - k(0.5) * c("visc")))))
            self.set(c("a_lp"), k(1.0) - ex(((-k(LV.TWO_PI)) * c("cut_l")) * IFS))
            self.set(c("fsk"), c("f") * (k(1.0) + (c("el") * k(2.5)) * mx(k(0.0), skE - V("sk_Es"))))
            self.set(c("perk"), FS * recip(c("fsk")))
            self.set(c("dmax"), c("perk") * k(1.0 / 16.0))
            self.powf("pp7", c("part"), k(0.7))
            self.set(c("apc"), k(-0.95) * c("pp7"))
            self.cmp((k(1.0) - c("apc")) * recip(k(1.0) + c("apc")), "GT", c("dmax"),
                     lambda: self.set(c("apc"), (k(1.0) - c("dmax")) * recip(k(1.0) + c("dmax"))))
            self.set(c("Lsk"), clipe((c("perk") - (k(1.0) - c("a_lp")) * recip(c("a_lp")))
                                     - (k(4.0) * (k(1.0) - c("apc"))) * recip(k(1.0) + c("apc")), 2.0, NB4))
            self.set(c("om"), k(1.0) - c("visc"))
            self.set(c("dsk"), (((k(0.05) + (c("om") * sqrt(c("om"))) * k(2.5)) * (k(0.5) + c("mass"))) * recip(c("damp_x")))
                     * (k(1.0) - k(0.8) * c("morph")))
            self.set(c("gsk"), exp2((k(-3.0) * k(LV.LOG2_10)) * recip(c("dsk") * c("fsk"))))
            self.set(c("nlk"), (k(1.0) + k(2.0) * c("inst")) + k(1.5) * c("stress"))
            self.set(c("inlk"), recip(c("nlk")))
            self.set(c("tf"), (k(LV.PI) * mn(c("sk_cut"), k(18000.0))) * IFS)
            self.tanf("g2", "tf")
            self.set(c("k2"), recip(k(0.6) + c("inst") * k(2.5)))
            self.set(c("b1"), recip(k(1.0) + c("g2") * (c("g2") + c("k2"))))
            self.set(c("b2c"), c("g2") * c("b1"))
            self.set(c("b3"), c("g2") * c("b2c"))
            self.ev(c("Lsk") * (k(0.03) + k(0.47) * c("pos")), 0)
            p.trunc(0, 0)
            p.iconst(12, 1)
            p.iop(0, 0, "MAX", 12)
            p.st(C["skd"], 0)
        self.icmp(mat, "EQ", 2, skin)
        self.wander(k(0.8) + k(3.0) * (k(1.0) - c("visc")), "wnd", 14, "2")

        def fluid():
            self.crv("melt", c("tn") * recip((k(0.4) + c("visc") * k(4.0)) * (k(0.5) + (k(1.0) - c("speedk")))), shape)
            self.set(c("fl_f"), c("f") * exp2(((-(k(1.0) - c("tens"))) * k(160.0 / 1200.0)) * c("melt")))
            self.set(c("fl_cut"), mn(k(16000.0), (c("fl_f") * (k(2.0) + (k(22.0) * c("tens")) * (k(1.0) - k(0.7) * c("melt"))))
                                     * (k(1.0) - k(0.5) * c("visc"))))
            self.set(c("fl_a"), k(1.0) - ex(((-k(LV.TWO_PI)) * c("fl_cut")) * IFS))
            self.set(c("fl_apc"), k(-0.5) * c("part") - (k(0.3) * c("melt")) * (k(0.5) + k(0.5) * V("wnd", 14)))
            self.set(c("perf"), FS * recip(c("fl_f")))
            self.set(c("dmx"), c("perf") * k(1.0 / 16.0))
            self.cmp((k(1.0) - c("fl_apc")) * recip(k(1.0) + c("fl_apc")), "GT", c("dmx"),
                     lambda: self.set(c("fl_apc"), (k(1.0) - c("dmx")) * recip(k(1.0) + c("dmx"))))
            self.set(c("fl_L"), clipe((c("perf") - (k(1.0) - c("fl_a")) * recip(c("fl_a")))
                                      - (k(4.0) * (k(1.0) - c("fl_apc"))) * recip(k(1.0) + c("fl_apc")), 2.0, NB4))
            self.set(c("dfl"), ((((k(0.3) + k(2.0) * (k(1.0) - c("visc"))) * (k(0.5) + c("mass"))) * (k(1.0) - k(0.5) * c("melt")))
                                * recip(c("damp_x"))) * (k(1.0) - k(0.8) * c("morph")))
            self.set(c("gfl"), exp2((k(-3.0) * k(LV.LOG2_10)) * recip(c("dfl") * c("fl_f"))))
            self.set(c("drate"), ((k(0.5) + (c("dens") * c("dens")) * k(30.0)) * (k(0.3) + k(0.7) * c("melt")))
                     * (k(1.0) + k(2.0) * c("stress")))
            self.set(c("drp_dec"), ex(-recip(((k(0.01) + k(0.05) * (k(1.0) - c("visc"))) + k(0.03) * c("grain")) * FS)))
        self.icmp(mat, "EQ", 3, fluid)
        self.ev((k(0.00015) + (c("oms") * c("oms")) * k(0.004)) * FS, 0)
        p.trunc(0, 0)
        p.iconst(12, 4)
        p.iop(0, 0, "MAX", 12)
        p.st(C["pw0"], 0)
        self.set(c("av_dec"), ex(-recip((k(0.01) + c("grain") * k(0.08)) * FS)))

        def wp():
            for kk in range(6):
                self.set(self.a("wpos", kk), k(0.25) + k(0.75) * ab(sinf((k(LV.PI) * k(kk + 1)) * (k(0.03) + k(0.47) * c("pos")))))
        self.icmp(mat, "EQ", 1, wp)

    def blk_players(self) -> None:
        """the filaments: how many, and each one's pitch this block (live: `nsec`, `sper`)"""
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        mode, qual, mat = V("L4", 2), V("L4", 7), V("L4", 0)
        self.iset(c("nsec"), 0)

        def ens():
            self.icmp(qual, "EQ", 0, lambda: self.set(c("qn"), k(LV.QN_MASS[0])),
                      lambda: self.icmp(qual, "EQ", 1, lambda: self.set(c("qn"), k(LV.QN_MASS[1])),
                                        lambda: self.set(c("qn"), k(LV.QN_MASS[2]))))
            self.ev((c("qn") * (k(0.25) + k(0.75) * c("voices"))) * (k(0.4) + k(0.6) * V("vel")) + k(0.5), 0)
            p.trunc(0, 0)
            p.iconst(12, 1)
            p.iop(0, 0, "MAX", 12)
            p.st(C["nsec"], 0)

        def solo():
            def on():
                self.icmp(qual, "EQ", 0, lambda: self.set(c("qn"), k(LV.QN_SOLO[0])),
                          lambda: self.icmp(qual, "EQ", 1, lambda: self.set(c("qn"), k(LV.QN_SOLO[1])),
                                            lambda: self.set(c("qn"), k(LV.QN_SOLO[2]))))
                self.ev(c("qn") * c("voices") + k(0.5), 0)
                p.trunc(0, 0)
                p.iconst(12, 1)
                p.iop(0, 0, "MAX", 12)
                p.st(C["nsec"], 0)
            self.cmp(c("voices"), "GT", k(0.01), lambda: self.icmp(mat, "EQ", 0, on, lambda: self.icmp(mat, "EQ", 2, on)))
        self.icmp(mode, "GE", 1, ens, solo)
        self.set(c("base_c"), (c("cents") - c("glp")) - c("ov"))
        # uk's divisor: max(1, nsec - 1)
        p.ld(0, C["nsec"])
        p.iconst(12, 1)
        p.iop(0, 0, "-", 12)
        p.iop(0, 0, "MAX", 12)
        p.iconst(12, 0)
        p.float_(0, 0, 12)
        p.st(C["nd"], 0)

        def players():
            p.ld(0, C["nsec"])
            p.st(C["cnt1"], 0)
            self.fz(c("kfl"))
            p.iconst(0, 0)
            p.st(C["kint"], 0)

            def one():
                self.player_ptrs()
                self.wander(k(0.3) + k(0.8) * c("drift"), "", 0, "1", x01=(self.Pk("sd0"), self.Pk("sd1")))
                self.set(self.Pk("svph"), self.Pk("svph") + ((k(4.0) + k(0.37) * c("kfl")) + k(2.0) * c("inst")) * k(LV.DT))
                self.floorw(self.Pk("svph"))

                def lock_on():
                    self.set(c("dphi"), V("vib_ph") - self.Pk("svph"))
                    self.floor_of(c("fl"), c("dphi") + k(0.5))
                    self.set(c("dphi"), c("dphi") - c("fl"))
                    self.set(self.Pk("svph"), self.Pk("svph") + (c("dphi") * c("lock")) * k(0.2))
                self.cmp(c("lock"), "GT", k(0.0), lock_on)
                self.set(c("uk"), (c("kfl") * recip(c("nd")) - k(0.5)) * k(2.0))
                self.set(c("sc"), k(1.0))
                self.fz(c("gk"))
                gest, distk, shape = V("L4", 1), V("L4", 3), V("L4", 5)

                def gl():
                    self.set(c("gp"), c("tn") * recip(k(0.4) + (k(1.0) - c("speedk")) * k(3.0)))

                    def d0():
                        self.set(c("gk"), V("gl_amt") * k(100.0))

                    def d1():
                        self.crv("cv", c("gp") * recip(k(1.0) + k(0.35) * c("uk")), shape)
                        self.set(c("gk"), ((c("gn") * k(1200.0)) * c("cv")) * (k(1.0) + k(0.15) * c("uk")))

                    def d2():
                        self.tabw(0, "ALTK", "kint")
                        p.st(C["alt"], 0)
                        self.set(c("gk"), ((V("gl_amt") * k(100.0)) * c("alt")) * (k(1.0) + k(0.75) * c("uk")))

                    def d3():
                        self.crv("pp", c("gp"), shape)
                        self.cmp(c("gn"), "GT", k(0.0), lambda: self.set(c("sc"), k(1.0) + (c("gn") * c("pp")) * k(3.0)),
                                 lambda: self.set(c("sc"), k(1.0) + c("gn") * c("pp")))
                    self.icmp(distk, "EQ", 0, d0, lambda: self.icmp(distk, "EQ", 1, d1,
                                                                    lambda: self.icmp(distk, "EQ", 2, d2, d3)))
                self.icmp(gest, "EQ", 6, gl)
                self.set(c("dr"), self.Pk("sd0") * (k(1.0) - c("lock")) + V("wnd", 0) * c("lock"))
                self.tabw(0, "SGNK", "kint")
                p.st(C["sgn"], 0)
                self.set(c("cc"), (((self.Pk("soff") * c("sc") + ((c("drift") * k(60.0)) * c("dr")) * (k(1.0) + c("loose")))
                                    + ((c("vibr") * k(40.0)) * V("vib_env")) * sinf(k(LV.TWO_PI) * self.Pk("svph"))) + c("gk"))
                         + ((c("stress") * k(30.0)) * V("wnd", 2)) * c("sgn"))
                self.set(c("fk"), V("f0") * exp2((c("cc") + c("base_c")) * k(1.0 / 1200.0)))
                self.set(Mv("i", 4, 0), mn(k(48000.0) * recip(mx(c("fk"), k(25.0))), k(float(LV.NSL - 4))))
                self.set(c("kfl"), c("kfl") + k(1.0))
                p.ld(9, C["kint"])
                p.iconst(12, 1)
                p.iop(9, 12, "+", 9)
                p.st(C["kint"], 9)
            self.ivloop("cnt1", one)
        p.ld(0, C["nsec"])
        p.ifz(0, "NE", players)
        self.set(c("prate"), k(5.0) + (c("dens") * c("dens")) * k(2500.0))
        self.set(c("sgn_p"), recip(sqrt(k(1.0) + ((c("prate") * (ab(V("bow")) * k(6.0) + c("imp") * k(40.0)))
                                                   + ((V("aval") * k(30.0)) * (c("dens") + k(0.2))) * c("prate")) * k(1.0 / 400.0))))

    def player_ptrs(self) -> None:
        """I3 = the voice + 4 kint (player kint's words), I4 = sper[kint]"""
        p, C = self.p, self.L.C
        p.ld(9, C["kint"])
        p.lsh(9, 9, 2)
        p.ld(12, C["vba"])
        p.iop(12, 12, "+", 9)
        p.seti(3, 12)
        p.iconst(12, self.L.A["sper"])
        p.iop(12, 12, "+", 9)
        p.seti(4, 12)

    # -- the samples ----------------------------------------------------------------------------
    def samples(self) -> None:
        p, C, L = self.p, self.L.C, self.L
        V, c = self.V, self.c
        gest, mat, mode = V("L4", 1), V("L4", 0), V("L4", 2)
        # bowc: BOW SCRAPE GLISS SWELL QUAKE; hpchain: not BOW GLISS SWELL
        self.iset(c("bowc"), 0)
        for g_ in (0, 1, 6, 8, 9):
            self.icmp(gest, "EQ", g_, lambda: self.iset(c("bowc"), 1))
        self.iset(c("hpch"), 1)
        for g_ in (0, 6, 8):
            self.icmp(gest, "EQ", g_, lambda: self.iset(c("hpch"), 0))
        self.set(c("prate_fs"), c("prate") * k(1.0 / 48000.0))
        self.iset(c("ens"), 0)
        self.icmp(mode, "EQ", 1, lambda: self.iset(c("ens"), 1))
        self.icmp(mode, "EQ", 2, lambda: self.iset(c("ens"), 1))
        p.iconst(0, 0)
        p.st(C["bad"], 0)
        p.ld(9, L.t_word)
        p.lsh(12, 9, 2)
        p.iconst(11, BUFFERS)
        p.iop(12, 11, "+", 12)
        p.seti(1, 12)
        p.ldi(0, 0, 1)
        p.st(C["outp"], 0)
        p.iconst(0, 0)
        p.st(C["si"], 0)

        def sample():
            self.set(c("nz"), bi1())
            self.fz(c("y"))
            self.fz(c("pv"))

            def pulse():
                self.ld(0, V("p_n"))
                p.iconst(12, 0)
                p.float_(0, 0, 12)
                p.st(C["pn"], 0)
                self.ld(0, V("p_i"))
                p.float_(0, 0, 12)
                p.st(C["pif"], 0)
                self.set(c("pv"), (V("p_a") * sqrt(k(8.0) * recip(c("pn")))) * sinf((k(LV.PI) * (c("pif") + k(0.5))) * recip(c("pn"))))
                self.icmp(V("p_i"), "LT", 24, lambda: self.set(c("pv"), c("pv") + ((c("nz") * c("snap")) * k(0.4)) * V("p_a")))
                self.ld(9, V("p_i"))
                p.iconst(12, 1)
                p.iop(9, 12, "+", 9)
                self.st(V("p_i"), 9)
            self.ld(0, V("p_i"))
            self.ld(1, V("p_n"))
            p.if_(0, "LT", 1, pulse, kind="i")
            self.fz(c("exv"))
            self.icmp(mat, "EQ", 0, self.s_fiber, lambda: self.icmp(mat, "EQ", 2, self.s_skin,
                      lambda: self.icmp(mat, "EQ", 1, self.s_silt, self.s_fluid)))
            self.s_players()
            self.s_tail()
            p.ld(9, C["si"])
            p.iconst(12, 1)
            p.iop(9, 12, "+", 9)
            p.st(C["si"], 9)
        p.loop(C["cnt0"], BLOCK, sample)

        def blown():
            self.zeros()
            self.fresh()
            self.iset(V("clear_at"), 0)
        p.ld(0, C["bad"])
        p.ifz(0, "NE", blown)

        def rests():
            self.cmp(V("amp"), "LT", k(LV.REST_AMP), lambda: self.iset(V("rest"), 1))
        self.icmp(V("gate"), "EQ", 0, rests)

    def bowf(self) -> None:
        """bow += (tgt - bow) (att if tgt != 0 else rel)"""
        V, c = self.V, self.c
        self.cmp(c("tgt"), "NE", k(0.0), lambda: self.set(c("ar"), c("att")), lambda: self.set(c("ar"), c("rel")))
        self.set(V("bow"), V("bow") + (c("tgt") - V("bow")) * c("ar"))

    def s_fiber(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        NBR = LV.NBR
        self.rd("a0", 0, NBR, V("wb"), c("db"))
        self.rd("a1", NBR, NBR, V("wk"), c("dn"))
        self.set(V("lp"), V("lp") + (c("a0") - V("lp")) * c("lpc"))

        def stiff():
            self.set(c("fy"), (c("fapc") * V("lp") + V("f_ax")) - c("fapc") * V("f_ay"))
            self.set(V("f_ax"), V("lp"))
            self.set(V("f_ay"), c("fy"))
            self.set(c("brr"), -c("fy") * c("lossm"))
        self.cmp(c("stiff"), "GT", k(0.0), stiff, lambda: self.set(c("brr"), -V("lp") * c("lossm")))
        self.set(c("nr"), -c("a1"))
        self.set(c("sv"), c("brr") + c("nr"))
        self.bowf()
        self.set(c("contact"), k(1.0))

        def nocon():
            self.set(c("contact"), mn(k(1.0), ab(V("bow")) * k(60.0)))
        self.cmp(c("tgt"), "EQ", k(0.0), lambda: self.icmp(c("bowc"), "EQ", 0, nocon))
        self.set(c("dv"), V("bow") - c("sv"))
        self.bow_k("btv", c("dv"), c("slope"), c("offset"))
        self.cmp(c("breakup"), "GT", k(0.0), lambda: self.set(c("btv"), c("btv") * (k(1.0) + (c("breakup") * k(0.6)) * c("nz"))))
        self.set(c("slip"), k(1.0) - c("btv"))
        self.set(c("gz"), c("nz"))

        def grit():
            self.ld(9, V("g_cnt"))
            p.iconst(12, 1)
            p.iop(9, 9, "-", 12)
            self.st(V("g_cnt"), 9)

            def hold():
                self.set(V("g_hold"), c("nz"))
                p.ld(0, C["ghold"])
                self.st(V("g_cnt"), 0)
            self.ld(9, V("g_cnt"))
            p.ifz(9, "LE", hold)
            self.set(c("gz"), V("g_hold") * k(1.4))
        p.ld(0, C["ghold"])
        p.iconst(1, 1)
        p.if_(0, "GT", 1, grit, kind="i")
        self.set(c("nv"), (c("dv") * c("btv") + (((c("gz") * c("scr")) * c("slip")) * k(0.06)) * (k(0.4) + c("pr"))) * c("contact"))

        def crackle():
            self.set(c("nv"), c("nv") + (bi2() * k(0.35)) * c("crk"))

        def cr_t():
            self.cmp(V("bow"), "NE", k(0.0), lambda: self.cmp(u2(), "LT", (c("crk") * c("crk")) * k(0.004), crackle))
        self.cmp(c("crk"), "GT", k(0.0), cr_t)
        self.set(c("nv"), c("nv") + c("pv") * k(0.9))
        self.wr(NBR, V("wk"), clipe(c("brr") + c("nv"), -2.0, 2.0))
        self.wr(0, V("wb"), clipe(c("nr") + c("nv"), -2.0, 2.0))
        self.bump_ptr(V("wb"), NBR)
        self.bump_ptr(V("wk"), NBR)
        self.set(c("y"), c("a0"))

        def squeal():
            self.rd("ah", 0, NBR, V("wb"), c("half"))
            self.set(c("y"), c("a0") * (k(1.0) - V("sq")) + (V("sq") * k(0.8)) * (c("a0") + c("ah")))
        self.cmp(V("sq"), "GT", k(0.01), squeal)

        def hpc():
            self.set(V("h1"), c("a_hp") * ((V("h1") + c("y")) - V("hx1")))
            self.set(V("hx1"), c("y"))
            self.set(V("h2"), c("a_hp") * ((V("h2") + V("h1")) - V("hx2")))
            self.set(V("hx2"), V("h1"))
            self.set(V("h3"), c("a_hp") * ((V("h3") + V("h2")) - V("hx3")))
            self.set(V("hx3"), V("h2"))
            self.set(V("h4"), c("a_hp") * ((V("h4") + V("h3")) - V("hx4")))
            self.set(V("hx4"), V("h3"))
            self.set(c("y"), V("h4"))
        self.icmp(c("hpch"), "NE", 0, hpc)
        self.set(c("exv"), c("nv"))
        self.set(c("hn"), c("nz") - V("hp"))
        self.set(V("hp"), V("hp") + (c("nz") - V("hp")) * k(0.25))
        self.set(c("y"), c("y") + ((c("hn") * c("air")) * ab(V("bow"))) * k(0.3))

    def s_allpass4(self, coef: str) -> None:
        V, c = self.V, self.c
        self.set(c("xa"), V("sk_lp"))
        for q in range(4):
            self.set(c("apy"), (c(coef) * c("xa") + V("sk_ap", 2 * q)) - c(coef) * V("sk_ap", 2 * q + 1))
            self.set(V("sk_ap", 2 * q), c("xa"))
            self.set(V("sk_ap", 2 * q + 1), c("apy"))
            self.set(c("xa"), c("apy"))

    def s_skin(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        NBR = LV.NBR
        self.bowf()
        self.rd("a", 0, NBR, V("wb"), c("Lsk"))
        self.set(V("sk_lp"), V("sk_lp") + (c("a") - V("sk_lp")) * c("a_lp"))
        self.s_allpass4("apc")
        self.set(c("vv"), tanh((c("xa") * c("gsk")) * c("nlk")) * c("inlk"))
        self.set(c("dcy"), (c("vv") - V("sk_dx")) + k(0.995) * V("sk_dy"))
        self.set(V("sk_dx"), c("vv"))
        self.set(V("sk_dy"), c("dcy"))
        self.set(c("vv"), c("dcy"))
        self.set(c("drive"), c("pv") * k(0.8))

        def bowed():
            self.set(c("dv"), V("bow") - c("vv") * k(0.5))
            self.bow_k("btv", c("dv"), c("slope"), c("offset"))
            self.set(c("reg"), recip(k(1.0) + k(6.0) * mx(k(0.0), V("sk_E") - (k(0.2) + k(0.5) * c("press")))))
            self.set(c("drive"), c("drive") + ((c("dv") * c("btv")) * k(1.6) + ((c("nz") * c("scr")) * (k(1.0) - c("btv"))) * k(0.03))
                     * c("reg"))
        self.cmp(V("bow"), "NE", k(0.0), bowed)

        def catch():
            self.set(c("drive"), c("drive") + (c("nz") * k(0.2)) * c("stress"))
        self.cmp(c("stress"), "GT", k(0.3), lambda: self.cmp(
            u2(), "LT", ((c("stress") * c("stress")) * c("stress")) * k(0.002), catch))
        self.set(c("exv"), c("drive"))

        def poke():
            self.ld(9, V("wb"))
            p.ld(10, C["skd"])
            p.iop(9, 9, "-", 10)
            p.iconst(12, NBR)
            p.ifz(9, "LT", lambda: p.iop(9, 12, "+", 9))
            p.st(C["jx"], 9)
            self.rd_word("jv", 0, c("jx"))
            self.wr(0, self.ci("jx"), c("jv") - c("pv") * k(0.8))
        self.cmp(c("pv"), "NE", k(0.0), poke)
        self.wr(0, V("wb"), clipe(c("vv") + c("drive"), -2.0, 2.0))
        self.bump_ptr(V("wb"), NBR)
        self.set(c("v3"), c("a") - V("sk_s2"))
        self.set(c("v1"), c("b1") * V("sk_s1") + c("b2c") * c("v3"))
        self.set(c("v2"), (V("sk_s2") + c("b2c") * V("sk_s1")) + c("b3") * c("v3"))
        self.set(V("sk_s1"), k(2.0) * c("v1") - V("sk_s1"))
        self.set(V("sk_s2"), k(2.0) * c("v2") - V("sk_s2"))
        self.set(c("y"), c("v2") * k(2.2) + ((c("nz") * c("air")) * k(0.02)) * (ab(V("bow")) + ab(c("pv"))))
        self.set(c("ee"), ab(c("y")) * k(2.5))
        self.skE_follow()
        self.set(V("sk_Es"), V("sk_Es") + (V("sk_E") - V("sk_Es")) * (k(0.00015) + k(0.0006) * (k(1.0) - c("mass"))))

    def skE_follow(self) -> None:
        V, c = self.V, self.c
        self.cmp(c("ee"), "GT", V("sk_E"), lambda: self.set(c("kk"), k(0.01)), lambda: self.set(c("kk"), k(0.0006)))
        self.set(V("sk_E"), V("sk_E") + (c("ee") - V("sk_E")) * c("kk"))
        self.cmp(V("sk_E"), "GT", k(1.0), lambda: self.set(V("sk_E"), k(1.0)))

    def rd_word(self, dst: str, line_off: int, idx: Mv) -> None:
        """c(dst) = the line's word idx"""
        p, C = self.p, self.L.C
        self.ld(9, idx)
        p.ld(11, C["lnb"])
        p.iconst(12, 4 * line_off)
        p.iop(11, 12, "+", 11)
        p.lsh(12, 9, 2)
        p.iop(12, 12, "+", 11)
        p.seti(1, 12)
        p.ldi(0, 0, 1)
        p.st(C[dst], 0)

    def s_silt(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        self.fz(c("d"))

        def particle():
            self.set(c("d"), ((((k(0.3) + k(0.7) * u1()) * (k(1.0) + (c("cohe") * k(2.0)) * V("burst"))) * k(0.012))
                              * (k(0.4) + c("press"))) * c("sgn_p"))
            self.set(V("aval"), mn(k(1.5), V("aval") + (c("cohe") * (k(0.25) + k(0.5) * c("stress"))) * (k(0.5) + k(0.5) * c("rosin"))))
        self.cmp(u1(), "LT", c("prate_fs") * ((ab(V("bow")) * k(6.0) + c("imp") * k(40.0))
                                              + (V("aval") * k(30.0)) * (c("dens") + k(0.2))), particle)
        self.set(V("aval"), V("aval") * c("av_dec"))
        self.set(c("d"), c("d") + c("pv") * k(0.08))
        self.set(c("exv"), c("d"))
        self.fz(c("acc"))
        self.set(c("pk"), k(1.0))
        self.set(c("hpart"), k(1.0) - c("part") * k(0.5))
        for kk in range(6):
            mc, ms = self.a("mc", kk), self.a("ms", kk)
            md0, md1 = V("md", 2 * kk), V("md", 2 * kk + 1)
            self.set(c("re"), mc * md0 - ms * md1)

            def exc(kk=kk):
                self.set(c("re"), c("re") + ((c("d") * (k(0.4) + k(0.6) * u1())) * c("pk")) * self.a("wpos", kk))
            p.ld(0, C["nm"])
            p.iconst(1, kk)
            p.if_(1, "LT", 0, exc, kind="i")
            self.set(c("im"), ms * md0 + mc * md1)
            self.set(md0, c("re"))
            self.set(md1, c("im"))
            self.set(c("acc"), c("acc") + c("im"))
            self.set(c("pk"), c("pk") * c("hpart"))
        self.set(c("y"), ((c("acc") * k(0.5)) * (k(1.0) - k(0.5) * c("morph")))
                 + (c("nz") * c("d")) * (c("grain") * k(2.0) + c("morph") * k(3.0)))
        self.set(V("hp"), V("hp") + (c("nz") - V("hp")) * k(0.3))
        self.set(c("y"), c("y") + ((V("hp") * ab(V("bow"))) * (c("scrap") * k(0.12) + c("air") * k(0.06))
                                   + ((c("nz") * V("aval")) * c("air")) * k(0.01)))
        self.bowf()

    def s_fluid(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        NBR = LV.NBR
        self.bowf()
        self.rd("a", 0, NBR, V("wb"), c("fl_L"))
        self.set(V("sk_lp"), V("sk_lp") + (c("a") - V("sk_lp")) * c("fl_a"))
        self.s_allpass4("fl_apc")
        self.set(c("vv"), c("xa") * c("gfl"))
        self.set(c("dcy"), (c("vv") - V("sk_dx")) + k(0.995) * V("sk_dy"))
        self.set(V("sk_dx"), c("vv"))
        self.set(V("sk_dy"), c("dcy"))
        self.set(c("vv"), c("dcy"))
        self.set(c("drive"), c("pv") * k(0.6))

        def bowed():
            self.set(c("dv"), V("bow") - c("vv") * k(0.5))
            self.bow_k("btv", c("dv"), c("slope"), c("offset"))
            self.set(c("reg"), recip(k(1.0) + k(6.0) * mx(k(0.0), V("sk_E") - (k(0.15) + k(0.4) * c("press")))))
            self.set(c("drive"), c("drive") + ((c("dv") * c("btv")) * k(1.2)) * c("reg"))
        self.cmp(V("bow"), "NE", k(0.0), bowed)

        def drip():
            self.ev(u2() * k(3.999), 0)
            p.trunc(0, 0)
            p.st(C["jb"], 0)
            self.set(c("uu"), u2())
            self.powf("pw", c("uu"), k(0.5) + c("pos") * k(1.5))
            self.ev(c("pw") * (k(1.0) + c("part") * k(6.0)), 0)
            p.trunc(0, 0)
            p.iconst(12, 1)
            p.iop(0, 12, "+", 0)
            p.iconst(12, 0)
            p.float_(0, 0, 12)
            p.st(C["khf"], 0)
            self.set(c("bf"), (c("fl_f") * c("khf")) * (k(1.0) + k(0.004) * bi2()))
            self.set(c("ba"), ((k(0.3) + k(0.7) * u2()) * (k(0.3) + c("press"))) * k(0.5))
            for j in range(4):
                def setj(j=j):
                    self.set(V("bub_f", j), c("bf"))
                    self.set(V("bub_a", j), c("ba"))
                    self.fz(V("bub_r", j))
                self.icmp(c("jb"), "EQ", j, setj)
            self.set(c("drive"), c("drive") + c("ba") * k(0.15))
            self.set(V("aval"), mn(k(1.5), V("aval") + c("cohe") * k(0.5)))

        def dtest():
            self.cmp(u2(), "LT", (c("drate") * (k(1.0) + V("aval") * k(4.0))) * k(1.0 / 48000.0), drip)
        self.icmp(V("gate"), "NE", 0, dtest, lambda: self.cmp(c("tn"), "LT", k(2.0), dtest))
        self.set(V("aval"), V("aval") * c("av_dec"))
        self.fz(c("drs"))
        for j in range(4):
            def bub(j=j):
                self.set(V("bub_r", j), V("bub_r", j) + k(1.0 / 48000.0))
                self.set(c("fj"), V("bub_f", j) * (k(1.0) + ((k(1.0) - c("visc")) * k(3.0)) * mn(V("bub_r", j), k(0.03))))
                self.set(V("bub_p", j), V("bub_p", j) + c("fj") * k(1.0 / 48000.0))
                self.floorw(V("bub_p", j))
                self.set(c("drs"), c("drs") + V("bub_a", j) * sinf(k(LV.TWO_PI) * V("bub_p", j)))
                self.set(V("bub_a", j), V("bub_a", j) * c("drp_dec"))
            self.cmp(V("bub_a", j), "GT", k(1e-4), bub)
        self.set(c("exv"), c("drive") + c("drs") * k(0.1))
        self.wr(0, V("wb"), clipe(c("vv") + c("drive"), -2.0, 2.0))
        self.bump_ptr(V("wb"), NBR)
        self.set(c("y"), c("a") * k(1.6) + c("drs") * k(0.35))
        self.set(V("hp"), V("hp") + (c("nz") - V("hp")) * k(0.08))
        self.set(c("y"), c("y") + ((V("hp") * (ab(V("bow")) + c("drs"))) * c("air")) * k(0.1))
        self.set(c("ee"), ab(c("a")) * k(2.5))
        self.skE_follow()

    def s_players(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        NBR, NSL = LV.NBR, LV.NSL
        mode, mat, gest = V("L4", 2), V("L4", 0), V("L4", 1)
        self.set(c("yprev"), c("y"))

        def any_():
            self.fz(c("sacc"))
            p.ld(0, C["nsec"])
            p.st(C["cnt2"], 0)
            self.fz(c("kfl"))
            p.iconst(0, 0)
            p.st(C["kint"], 0)

            def one():
                self.player_ptrs()
                # the player's line: 2 NBR + kint NSL words in
                p.ld(9, C["kint"])
                p.iconst(12, NSL)
                p.mul_ssi(9, 9, 12)
                p.iconst(12, 2 * NBR)
                p.iop(9, 12, "+", 9)
                p.st(C["loff"], 9)
                Pk = self.Pk
                self.rd_dyn("a", NSL, Pk("sw"), Mv("i", 4, 0))
                self.set(Pk("slp"), Pk("slp") + (c("a") - Pk("slp")) * c("lpc"))

                def inv():
                    self.set(c("v_s"), -Pk("slp") * k(0.996))

                def upright():
                    self.set(c("v_s"), (Pk("slp") * k(0.996) - Pk("sdx")) + k(0.995) * Pk("sdy"))
                    self.set(Pk("sdx"), Pk("slp") * k(0.996))
                    self.set(Pk("sdy"), c("v_s"))
                self.icmp(mode, "EQ", 2, inv, upright)

                def symp():
                    self.set(c("nvk"), (c("yprev") * k(0.03)) * (k(0.4) + k(1.2) * c("cohe")))

                def bowed():
                    self.tabw(0, "FACK", "kint")
                    p.st(C["fac0"], 0)
                    self.set(c("fac"), k(1.0) + ((c("fac0") * (k(1.0) - c("lock"))) * (k(1.0) + k(2.0) * c("loose"))))
                    self.set(c("ent"), k(1.0))
                    self.icmp(gest, "EQ", 8, lambda: self.set(c("ent"), clipe(c("entry") * fi(self.ci("nsec")) - c("kfl"), 0.0, 1.0)))
                    self.cmp(c("tgt"), "NE", k(0.0), lambda: self.set(c("ar"), c("att")), lambda: self.set(c("ar"), c("rel")))
                    self.set(Pk("sbow"), Pk("sbow") + ((c("tgt") * c("fac")) * c("ent") - Pk("sbow")) * c("ar"))
                    self.set(c("dvk"), Pk("sbow") - c("v_s"))
                    self.bow_k("btk", c("dvk"), c("slope") * k(1.1), c("offset"))
                    self.set(c("ck"), k(1.0))

                    def nocon():
                        self.set(c("ck"), mn(k(1.0), ab(Pk("sbow")) * k(60.0)))
                    self.cmp(c("tgt"), "EQ", k(0.0), lambda: self.icmp(c("bowc"), "EQ", 0, nocon))
                    self.set(c("nvk"), (c("dvk") * c("btk") + ((c("nz") * c("scr")) * (k(1.0) - c("btk"))) * k(0.05)) * c("ck"))

                    def split():
                        self.tabw(0, "IMPK", "kint")
                        p.st(C["impk"], 0)
                        self.ld(0, self.ci("si"))
                        p.iconst(12, 0)
                        p.float_(0, 0, 12)
                        p.st(C["sif"], 0)
                        self.set(c("nvk"), c("nvk") + ((c("imp_sub") * k(0.25)) * c("impk")) * (k(1.0) - c("sif") * k(1.0 / 6.0)))
                    self.cmp(c("imp_sub"), "GT", k(0.0), lambda: self.icmp(self.ci("si"), "LT", 6, split))

                def other():
                    self.set(c("nvk"), c("exv") * k(0.3))
                self.icmp(mode, "EQ", 0, symp, lambda: self.icmp(mat, "EQ", 0, bowed,
                                                                 lambda: self.icmp(mat, "EQ", 1, bowed, other)))

                def strikes():
                    def tick():
                        self.ld(9, Pk("scnt"))
                        p.iconst(12, 1)
                        p.iop(9, 12, "+", 9)
                        self.st(Pk("scnt"), 9)

                        def add():
                            self.ld(0, Pk("scnt"))
                            p.iconst(12, 0)
                            p.float_(0, 0, 12)
                            p.st(C["scf"], 0)
                            self.ld(0, self.ci("pw0"))
                            p.float_(0, 0, 12)
                            p.st(C["pwf"], 0)
                            self.set(c("nvk"), c("nvk") + ((V("simp") * k(0.5)) * sqrt(k(8.0) * recip(c("pwf"))))
                                     * sinf((k(LV.PI) * c("scf")) * recip(c("pwf"))))
                        self.ld(9, Pk("scnt"))
                        p.ifz(9, "GT", add)
                    self.ld(0, Pk("scnt"))
                    p.ld(1, C["pw0"])
                    p.if_(0, "LT", 1, tick, kind="i")
                self.cmp(V("simp"), "GT", k(0.0), lambda: self.icmp(mode, "GE", 1, strikes))
                self.wr_dyn(Pk("sw"), clipe(c("v_s") + c("nvk"), -2.0, 2.0))
                self.bump_ptr(Pk("sw"), NSL)
                self.set(c("sacc"), c("sacc") + c("a"))
                self.set(c("kfl"), c("kfl") + k(1.0))
                p.ld(9, C["kint"])
                p.iconst(12, 1)
                p.iop(9, 12, "+", 9)
                p.st(C["kint"], 9)
            self.ivloop("cnt2", one)

            def solo_mix():
                self.set(c("y"), c("y") + (c("sacc") * k(0.6)) * c("voices"))

            def ens_mix():
                self.icmp(c("ens"), "NE", 0, lambda: self.set(c("ym"), k(0.55)), lambda: self.set(c("ym"), k(0.8)))
                self.set(c("y"), c("y") * c("ym") + (c("sacc") * k(1.6)) * recip(sqrt(fi(self.ci("nsec"))) + k(1.0)))
            self.icmp(mode, "EQ", 0, solo_mix, ens_mix)
        p.ld(0, C["nsec"])
        p.ifz(0, "NE", any_)

    def rd_dyn(self, dst: str, n: int, wptr: Mv, d: Mv) -> None:
        """rd on the player's line (its word offset in c('loff'))"""
        p, C = self.p, self.L.C
        # the same as rd with a run-time line offset
        self.set(self.c("rdd"), d)
        self.ld(0, self.c("rdd"))
        p.trunc(1, 0)
        p.iconst(12, 0)
        p.float_(2, 1, 12)
        p.fop(0, 0, "-", 2)
        p.st(C["rfr"], 0)
        self.ld(9, wptr)
        p.iop(9, 9, "-", 1)
        p.iconst(12, n)
        p.ifz(9, "LT", lambda: p.iop(9, 12, "+", 9))
        p.iconst(13, 1)
        p.iop(10, 9, "-", 13)
        p.ifz(10, "LT", lambda: (p.iconst(12, n), p.iop(10, 12, "+", 10)))
        p.ld(11, C["lnb"])
        p.ld(12, C["loff"])
        p.lsh(12, 12, 2)
        p.iop(11, 12, "+", 11)
        p.lsh(12, 9, 2)
        p.iop(12, 12, "+", 11)
        p.seti(1, 12)
        p.ldi(3, 0, 1)
        p.lsh(12, 10, 2)
        p.iop(12, 12, "+", 11)
        p.seti(1, 12)
        p.ldi(4, 0, 1)
        p.fop(4, 4, "-", 3)
        p.ld(5, C["rfr"])
        p.fop(4, 4, "*", 5)
        p.fop(3, 3, "+", 4)
        p.st(C[dst], 3)

    def wr_dyn(self, idx: Mv, val: E) -> None:
        p, C = self.p, self.L.C
        self.ev(w(val), 0)
        self.ld(9, idx)
        p.ld(11, C["lnb"])
        p.ld(12, C["loff"])
        p.lsh(12, 12, 2)
        p.iop(11, 12, "+", 11)
        p.lsh(12, 9, 2)
        p.iop(12, 12, "+", 11)
        p.seti(1, 12)
        p.sti(0, 1, 0)

    def s_tail(self) -> None:
        p, C = self.p, self.L.C
        V, c = self.V, self.c
        mode = V("L4", 2)

        def swarm():
            def gather():
                self.set(V("burst"), mn(k(1.5), V("burst") + k(0.5) * (k(0.3) + c("cohe"))))
            self.cmp(u1(), "LT", c("prate_fs") * (ab(V("bow")) * k(8.0) + k(0.2)), gather)
            self.set(V("burst"), V("burst") * (k(0.9995) - (k(1.0) - c("cohe")) * k(0.002)))
            self.set(V("hp"), V("hp") + (c("nz") - V("hp")) * (k(0.05) + k(0.4) * c("part")))
            self.set(c("y"), c("y") + ((V("hp") * V("burst")) * k(0.12)) * (k(0.3) + c("grain")))
        self.icmp(mode, "EQ", 3, swarm)

        def cloud():
            def gather():
                self.set(V("cl_b"), mn(k(1.5), V("cl_b") + k(0.5) * (k(0.3) + c("cohe"))))
            self.cmp(u2(), "LT", c("prate_fs") * (ab(V("bow")) * k(8.0) + k(0.1)), gather)
            self.set(V("cl_b"), V("cl_b") * (k(0.9995) - (k(1.0) - c("cohe")) * k(0.002)))
            self.set(V("cl_hp"), V("cl_hp") + (c("nz") - V("cl_hp")) * (k(0.05) + k(0.4) * c("part")))
            self.set(c("y"), c("y") + ((((V("cl_hp") * V("cl_b")) * k(0.12)) * (k(0.3) + c("grain"))) * (c("dens") - k(0.25)))
                     * k(1.0 / 0.75))
        self.icmp(c("ens"), "NE", 0, lambda: self.cmp(c("dens"), "GT", k(0.25), cloud))
        self.fz(c("bo"))
        for kk in range(4):
            b0, b1 = V("body", 2 * kk), V("body", 2 * kk + 1)
            self.set(c("re"), (self.a("bc", kk) * b0 - self.a("bs", kk) * b1) + c("y") * k(LV.BGN[kk]))
            self.set(c("im"), self.a("bs", kk) * b0 + self.a("bc", kk) * b1)
            self.set(b0, c("re"))
            self.set(b1, c("im"))
            self.set(c("bo"), c("bo") + c("im"))
        self.set(c("y"), c("y") + (c("bodyk") * c("bo")) * k(1.5))
        self.set(c("v3"), c("y") - V("fm2"))
        self.set(c("v1"), c("fa1") * V("fm1") + c("fa2") * c("v3"))
        self.set(c("v2"), (V("fm2") + c("fa2") * V("fm1")) + c("fa3") * c("v3"))
        self.set(V("fm1"), k(2.0) * c("v1") - V("fm1"))
        self.set(V("fm2"), k(2.0) * c("v2") - V("fm2"))
        self.set(c("y"), c("y") * (k(1.0) - c("form") * k(0.6)) + (c("v1") * c("form")) * k(1.8))
        self.set(c("ee"), mn(k(1.0), ab(c("exv")) * k(4.0)))
        self.cmp(c("ee"), "GT", V("env_e"), lambda: self.set(c("kk"), k(0.02)), lambda: self.set(c("kk"), k(0.0015)))
        self.set(V("env_e"), V("env_e") + (c("ee") - V("env_e")) * c("kk"))

        def gate_on():
            self.set(V("amp"), V("amp") + (k(1.0) - V("amp")) * k(0.01))

        def gate_off():
            self.set(V("amp"), V("amp") + (k(0.0) - V("amp")) * k(0.0004))
        self.icmp(V("gate"), "NE", 0, gate_on, gate_off)
        self.set(c("yo"), tanh(c("y") * k(0.6)) * V("amp"))

        def faded():
            # the steal's ramp: 1 - (i + 1)/32
            self.ld(0, self.ci("si"))
            p.iconst(12, 1)
            p.iop(0, 12, "+", 0)
            p.iconst(12, 0)
            p.float_(0, 0, 12)
            p.st(C["sif"], 0)
            self.set(c("yo"), c("yo") * (k(1.0) - c("sif") * k(1.0 / LV.SUB)))
        self.icmp(c("fadeo"), "NE", 0, faded)
        self.ld(0, c("yo"))
        p.ld(12, C["outp"])
        p.seti(3, 12)
        p.sti(0, 3, 0)
        p.iconst(1, 0x7F800000)
        p.iop(2, 0, "AND", 1)
        p.if_(2, "EQ", 1, lambda: (p.iconst(3, 1), p.st(C["bad"], 3)), kind="i")
        p.ld(13, C["outp"])
        p.iconst(12, 4)
        p.iop(13, 12, "+", 13)
        p.st(C["outp"], 13)


def voice(p, L: Layout, t: int | None = None) -> SG:
    g = SG(p, L)
    saved = p.scr_on
    p.iconst(0, L.base5)
    p.seti(5, 0, "the scratch's base + WIN words")
    p.scr_on = True
    g.voice(t)
    p.scr_on = saved
    return g


def run_voice(L: Layout, read, t: int, mem=None):
    mem = mem or Mem(read)
    p = FP_.FProg("run", mem=mem)
    p.pool = {}
    p.spill = None
    p.scr = (L.scratch, L.scratch_end, L.base5)
    voice(p, L, t)
    return p, mem


def layout() -> Layout:
    from ..waverider import dsp
    return Layout(FP_.layout(), dsp.SILT_TABLES_DDR, dsp.SILT_DELAY_DDR)
