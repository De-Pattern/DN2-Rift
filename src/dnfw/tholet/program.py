"""THOLET's DSP program (machine type 23): `dnfw.tholet.live.Voice` on the SHARC, in PERC's two-backend
DSL on FASCIA's expression compiler with ORGAN's leaves (exp2f, expf, sin_turns), as DIGIDRUM's is. The
same calls are the assembly text and, run in Python, its exact model; test_tholet_program holds the run
mode to live.Voice bit for bit. The concept is Error Kit's.

**Where it runs.** Inside FASCIA's program (fascia.asm), as ORGAN, SILT, LIGATURE and DIGIDRUM do:
FASCIA's walk renders a slot whose frame type word is 23 with this, under the same guard and steal
bookkeeping. Its voice lives in the slot's FASCIA state; the walk's type change clears its magic.

**The block** (live.Voice.block): the sixteen knobs (KREC); the ring's clearing (512 words a block
for its first 32 blocks); a trig, a knob change or a note-off (the partials tuned, the damper); then
three passes: the strike (32 samples into `sk`), the strings (24 two-pole resonators, each over the
32 samples, summed into `acs`), and the voice (the bark, the rise, the cloud, the level) into the
slot's buffer, with its peak (the voice rests when quiet).

**Memory.** The voice in the slot's FASCIA state: its words, 24 resonator records (y1 y2 c0 c1 cw amp)
and 8 grain records (pos inc w d n). The tables in DDR at THOLET_TABLES_DDR (the knobs' records, mu-law's
256 levels, the six strikes' bytes, the partials' constants, log2 of the velocities, the strikes'
ratios); the cloud's ring (16,384 floats a slot) at THOLET_RING_DDR.
"""
from __future__ import annotations

import pathlib
import re
import struct

import numpy as np

from ..fascia import program as FP_
from ..fascia.program import E, Kc, Mv, Fn, St, w, fi, recip, mn, mx, _xs_leaf, STRIDE, BLOCK, BUFFERS
from ..organ import program as OP
from ..organ.program import exp2f, expf, sin_turns
from ..perc import program as PP
from ..perc.dsl import Mem, f32, bits
from ..ligature.program import _lsh_by
from . import live as LV

F = np.float32
TYPE = 23
NK = 16
MAGIC = 0x54484F21                     # 'THO!'
assert BLOCK == LV.SUB
CTRL = LV.CONTROLS
NR, NG, RING = LV.NR, LV.NG, LV.RING
RW, GW = 6, 5                          # a resonator's words (y1 y2 c0 c1 cw amp), a grain's (pos inc w d n)
NCLR = RING // 512

# -- the voice's words (in the slot's FASCIA state) ------------------------------------------------
VOICE = St().w("on", "pending", "fading")
assert [VOICE[x] for x in ("on", "pending", "fading")] == [FP_.VOICE[x] for x in ("on", "pending", "fading")]
VOICE.w("magic", "rng", "clr", "note", "vel", "vl2", "gate", "hp", "hr", "hk", "lz", "tz", "te", "rise",
        "env", "ed", "t60", "f0", "quiet", "wp", "nxt", "fph").w("sig", n=len(LV.RETUNE))
VOICE.w("res", n=NR * RW).w("gr", n=NG * GW)
RESET_FROM = VOICE["hp"]               # reset(): every word from hp to the end (the rest set by the trig)
VOICE_WORDS = VOICE.n
assert 4 * VOICE_WORDS <= STRIDE

# -- the tables (DDR) ------------------------------------------------------------------------------
NHB = (LV.HIT_N + 3) // 4              # a strike's words (four mu-law bytes each, the first lowest)
RROW = 8                               # a partial's row: p, p - 1, the hammer's place, its T60 share,
                                       # tine (1/0), the tine's ratio, level, T60 share
TAB = {"KREC": (0, 4 * NK)}
TAB["MULAW"] = (TAB["KREC"][1], 256)
TAB["HITS"] = (TAB["MULAW"][0] + 256, LV.NH * NHB)
TAB["PART"] = (TAB["HITS"][0] + LV.NH * NHB, NR * RROW)
TAB["VLOG2"] = (TAB["PART"][0] + NR * RROW, 128)
TAB["HINV"] = (TAB["VLOG2"][0] + 128, LV.NH)
TABLE_WORDS = TAB["HINV"][0] + LV.NH


def _krec() -> list[int]:
    from . import machines as TM
    from ..fascia import machines as FM
    out = []
    for cn in TM.CONTROLS:
        _rid, slot, lo, top = FM.SLOTS[TM.RIDES[cn]]
        assert lo == 0
        n = len(TM.HITS) if cn == "HAMR" else 0
        scale = 0 if top == 127 else bits(f32(254.0 / (200 if top == 100 else 240)))
        out += [168 + 2 * slot, top, n, scale]
    return out


def _part_rows() -> list[int]:
    out = []
    for i in range(NR):
        p = i % LV.NP_ + 1
        tine = p <= 4
        tr, ta, td = LV.TINE[p - 1] if tine else (F(0.0), F(0.0), F(0.0))
        out += [bits(f32(float(p))), bits(f32(float(p - 1))), bits(f32(float(LV.HPOS[p - 1]))),
                bits(f32(float(LV.RP[p - 1]))), int(tine), bits(f32(float(tr))), bits(f32(float(ta))),
                bits(f32(float(td)))]
    return out


def tables_bytes() -> bytes:
    hits = []
    for k in range(LV.NH):
        b = LV.HIT_BYTES[k] + bytes(4 * NHB - LV.HIT_N)
        hits += list(struct.unpack(f"<{NHB}I", b))
    ws = (_krec() + [bits(f32(float(x))) for x in LV.MULAW] + hits + _part_rows()
          + [bits(f32(float(x))) for x in LV.VLOG2] + [bits(f32(float(x))) for x in LV.HINV])
    assert len(ws) == TABLE_WORDS
    return struct.pack(f"<{TABLE_WORDS}I", *ws)


def write_ddr_json() -> None:
    import json
    from . import ddr
    words = [f"{x:08x}" for x in struct.unpack(f"<{TABLE_WORDS}I", tables_bytes())]
    ddr.DDR_JSON.write_text(json.dumps({"note": "generated by scripts/gen_fascia_asm.py from dnfw.tholet; do not edit",
                                        "words": words}) + "\n", encoding="utf-8", newline="\n")


def k(x) -> Kc:
    return Kc(float(F(x)))


# -- the block's words (FASCIA's transient arrays) --------------------------------------------------
_SRC = pathlib.Path(__file__).read_text(encoding="utf-8")
WORDS = tuple(sorted(set(re.findall(r'\bc\("([A-Za-z_0-9]+)"\)', _SRC)) | set(re.findall(r'\bC\["([A-Za-z_0-9]+)"\]', _SRC))
                     | {"trig", "nn", "vv", "k146", "tmp0", "tmp1", "cnt0", "cnt1", "cnt2", "krp", "kep", "vba",
                        "outp", "off", "ivel", "i0f", "gif"} | {f"sg{j}" for j in range(len(LV.RETUNE))}
                     | set(re.findall(r'\b(?:ptr|bump|vaddr|floor_int|ring_at|hit_byte)\((?:\d+, )?"([A-Za-z_0-9]+)"', _SRC))
                     | set(re.findall(r'hit_byte\("[a-z0-9]+", "([a-z0-9]+)"\)', _SRC))
                     | set(re.findall(r'tword\(\d+, "[A-Z0-9]+", "([a-z0-9]+)"', _SRC))))
ARRAYS = {"eff": NK, "sk": BLOCK, "acs": BLOCK}


class Layout:
    def __init__(self, fascia: FP_.Layout, tables: int, ring: int):
        self.fl = fascia
        self.state, self.state2 = fascia.state, fascia.state2
        self.t_word = fascia.C["t"]
        self.stolen, self.strikes = fascia.stolen, fascia.strikes
        self.tables = tables
        self.ring = ring                       # THOLET_RING_DDR: RING floats a slot
        at = fascia.arrays
        self.C = {}
        for name in WORDS:
            self.C[name] = at
            at += 4
        self.A = {}
        for name, n in ARRAYS.items():
            self.A[name] = at
            at += 4 * n
        self.words_end = at
        assert at <= fascia.scratch_end, (at - fascia.scratch_end, "THOLET's words must fit in FASCIA's arrays")
        self.scratch, self.scratch_end, self.base5 = fascia.scratch, fascia.scratch_end, fascia.base5
        self.rets = fascia.rets


TLEAF = {"tun": _xs_leaf("tun", 2, VOICE["rng"], "u01")}


def u01() -> E:
    return Fn("tun", Kc(0.0))


OFF_WORD = 0x25C4B0                     # the frame's mask 36: the note-off, low half, bit t
LN60 = float(LV.LN60)
DT = float(LV.DT)


class TG(OP.OG):
    """FASCIA's compiler with ORGAN's leaves and THOLET's dice"""

    def c(self, name) -> Mv:
        return Mv("a", self.L.C[name])

    def call_at(self, name: str, r: int) -> None:
        if name not in TLEAF:
            return super().call_at(name, r)
        p = self.p
        if r == 0:
            TLEAF[name](self)
            return
        p.fpass(r + 1, 0)
        p.fpass(0, r)
        TLEAF[name](self)
        p.fpass(r, 0)
        p.fpass(0, r + 1)

    def V(self, name, j: int = 0) -> Mv:
        return Mv("i", 2, VOICE[name] + j)

    def Vi(self, name, j: int = 0) -> Mv:
        return Mv("i", 2, VOICE[name] + j, isint=True)

    def a(self, arr, j) -> Mv:
        return Mv("a", self.L.A[arr] + 4 * j)

    def e(self, cn) -> Mv:
        return self.a("eff", CTRL.index(cn))

    def q(self, cn) -> E:
        return self.e(cn) * k(LV.INV127)

    def bump(self, word: str, by: int) -> None:
        p, C = self.p, self.L.C
        p.ld(13, C[word])
        p.iconst(12, by)
        p.iop(13, 12, "+", 13)
        p.st(C[word], 13)

    def ptr(self, ireg: int, word: str) -> None:
        self.p.ld(12, self.L.C[word])
        self.p.seti(ireg, 12)

    def ivloop(self, cnt: str, body) -> None:
        FP_.FP.ivloop(self, cnt, body)

    def vaddr(self, word: str, field: str) -> None:
        """C[word] = the voice's address of FIELD"""
        p, C = self.p, self.L.C
        p.ld(12, C["vba"])
        p.iconst(13, 4 * VOICE[field])
        p.iop(12, 13, "+", 12)
        p.st(C[word], 12)

    def floor_int(self, dst: str, e) -> None:
        """C[dst] = (int) floorf(e), e >= 0; and c(dst + 'f') = floorf(e)"""
        p, C = self.p, self.L.C
        self.ev(w(e), 0)
        p.fpass(15, 0)
        OP._floor_f(p, 15, 14)
        p.st(C[dst + "f"], 14)
        p.trunc(14, 14)
        p.st(C[dst], 14)

    def tword(self, d: int, tab: str, idx_word: str | None, off: int = 0, shift: int = 2) -> None:
        """Rd = DM(tables + 4 TAB[tab] + (C[idx_word] << shift) + 4 off)"""
        p, C = self.p, self.L.C
        p.iconst(12, self.L.tables + 4 * (TAB[tab][0] + off))
        if idx_word is not None:
            p.ld(13, C[idx_word])
            p.lsh(13, 13, shift)
            p.iop(12, 13, "+", 12)
        p.seti(1, 12)
        p.ldi(d, 0, 1)

    # -- the voice's block ---------------------------------------------------------------------------
    def voice(self, t: int | None) -> None:
        p, C, L = self.p, self.L.C, self.L
        V = self.V
        if p.run:
            p.iconst(9, t)
            p.st(L.t_word, 9)
        self.vbase()
        self.read_note()
        self.read_vel()
        p.ld(0, OFF_WORD)
        p.iconst(1, 1)
        p.ld(9, L.t_word)
        PP._shift_by(p, 1, 9)
        p.iop(0, 0, "AND", 1)
        p.st(C["off"], 0)
        self.ld(0, V("magic"))
        p.iconst(1, MAGIC)
        p.if_(0, "NE", 1, self.fresh, kind="i")
        self.stolen_check()
        self.read_knobs()
        self.rt("t_block", self.block)

    def vbase(self) -> None:
        OP.OG.vbase(self)
        self.p.st(self.L.C["vba"], 12)

    def read_vel(self) -> None:
        """the trig's velocity, 0..127 (the frame's header word 52 + 2t, >> 8), as an int"""
        p, C, L = self.p, self.L.C, self.L
        p.ld(9, L.t_word)
        p.iop(10, 9, "+", 9)
        PP.half(p, 8, FP_.VEL_OFFSET, 10)
        p.lsh(8, 8, -8)
        p.iconst(12, 127)
        p.iop(8, 8, "MIN", 12)
        p.iconst(12, 0)
        p.iop(8, 8, "MAX", 12)
        p.st(C["ivel"], 8)

    def stolen_check(self) -> None:
        p = self.p
        self._slot_word(self.L.stolen)
        p.ldi(0, 0, 1)

        def rest():
            p.iconst(0, 0)
            p.sti(0, 1, 0)
            self.iset(self.V("on"), 0)
        p.ifz(0, "NE", rest)

    def fresh(self) -> None:
        """live.Voice(t): every word zero, the seed, the ring's clearing to do, the magic"""
        p, L = self.p, self.L
        p.ld(12, L.C["vba"])
        p.seti(4, 12)
        p.fconst(5, 0.0)
        p.loop_r(10, VOICE_WORDS, lambda: p.stpost(4, 5), one=11)
        # seed = 0x74686f00 + 0x01000193 (t + 1), or 1
        p.ld(9, L.t_word)
        p.iconst(12, 1)
        p.iop(9, 9, "+", 12)
        p.iconst(12, 0x01000193)
        p.mul_ssi(0, 9, 12)
        p.ipass(8, 0)
        p.iconst(12, 0x74686F00)
        p.iop(0, 8, "+", 12)
        p.ifz(0, "EQ", lambda: p.iconst(0, 1))
        self.st(self.V("rng"), 0)
        p.iconst(0, NCLR)
        self.st(self.Vi("clr"), 0)
        self.reset()
        p.iconst(0, MAGIC)
        self.st(self.V("magic"), 0)

    def reset(self) -> None:
        """live.Voice.reset: hp .. the end zero; env 1, ed 1, f0 261.6, nxt 960, vel 1"""
        p, L = self.p, self.L
        V = self.V
        p.ld(12, L.C["vba"])
        p.iconst(13, 4 * RESET_FROM)
        p.iop(12, 13, "+", 12)
        p.seti(4, 12)
        p.fconst(5, 0.0)
        p.loop_r(10, VOICE_WORDS - RESET_FROM, lambda: p.stpost(4, 5), one=11)
        self.set(V("env"), k(1.0))
        self.set(V("ed"), k(1.0))
        self.set(V("f0"), k(261.6))
        self.set(V("vel"), k(1.0))
        self.fz(V("vl2"))
        self.fz(V("gate"))
        p.iconst(0, 960)
        self.st(self.Vi("nxt"), 0)
        p.iconst(0, -1)                        # sig: none (live's None) -- no knob value is -1
        for j in range(len(LV.RETUNE)):
            self.st(self.Vi("sig", j), 0)

    def read_knobs(self) -> None:
        """the sixteen knobs: SILT's loop over KREC (HAMR an option, 0..5)"""
        p, C, L = self.p, self.L.C, self.L
        p.ld(9, L.t_word)
        PP.t146(p, 10, 9)
        p.st(C["k146"], 10)
        p.iconst(0, NK)
        p.st(C["cnt1"], 0)
        p.iconst(0, L.tables + 4 * TAB["KREC"][0])
        p.st(C["krp"], 0)
        p.iconst(0, L.A["eff"])
        p.st(C["kep"], 0)

        def one():
            p.ld(12, C["krp"])
            p.seti(3, 12)
            p.ldi(10, 0, 3)
            p.ld(12, C["k146"])
            p.iop(10, 12, "+", 10)
            PP.half(p, 4, 0, 10)
            p.lsh(4, 4, -8)
            p.ld(12, C["krp"])
            p.seti(3, 12)
            p.ldi(12, 1, 3)
            p.iop(4, 4, "MIN", 12)
            p.ldi(5, 3, 3)

            def scaled():
                p.iconst(12, 0)
                p.float_(4, 4, 12)
                p.fop(4, 4, "*", 5)
                p.fconst(6, 0.502)
                p.fop(4, 4, "+", 6)
                p.trunc(4, 4)
            p.ifz(5, "NE", scaled)
            p.ld(12, C["krp"])
            p.seti(3, 12)
            p.ldi(12, 2, 3)

            def opt():
                p.mul_ssi(4, 4, 12)
                p.lsh(4, 4, -7)
                p.iconst(13, 1)
                p.iop(12, 12, "-", 13)
                p.iop(4, 4, "MIN", 12)
            p.ifz(12, "NE", opt)
            p.iconst(12, 0)
            p.float_(4, 4, 12)
            p.ld(12, C["kep"])
            p.seti(3, 12)
            p.sti(0, 3, 4)
            self.bump("krp", 16)
            self.bump("kep", 4)
        self.ivloop("cnt1", one)

    def zeros(self) -> None:
        OP.OG.zeros(self)

    # -- live.Voice.block ------------------------------------------------------------------------------
    def block(self) -> None:
        p, C, L = self.p, self.L.C, self.L
        V, Vi, c = self.V, self.Vi, self.c
        # the ring's clearing (the DSP's 32 blocks; live counts them): chunk 32 - clr, then clr - 1
        def clear():
            self.ld(0, Vi("clr"))
            p.iconst(12, NCLR)
            p.iop(0, 12, "-", 0)               # NCLR - clr
            p.lsh(0, 0, 11)                    # x 2048 bytes
            self.ring_base(8)
            p.iop(0, 8, "+", 0)
            p.seti(4, 0)
            p.fconst(5, 0.0)
            p.loop_r(10, 512, lambda: p.stpost(4, 5), one=11)
            self.ld(8, Vi("clr"))
            p.iconst(12, 1)
            p.iop(0, 8, "-", 12)
            self.st(Vi("clr"), 0)
        self.icmp(Vi("clr"), "GT", 0, clear)
        # the knobs that retune: their signature against the last
        self.iset(c("chg"), 0)
        for j, cn in enumerate(LV.RETUNE):
            self.ev(self.e(cn), 0)
            p.trunc(0, 0)
            p.st(C[f"sg{j}"], 0)
            self.ld(1, Vi("sig", j))
            p.if_(0, "NE", 1, lambda: self.iset(c("chg"), 1), kind="i")

        def store_sig():
            for j in range(len(LV.RETUNE)):
                p.ld(0, C[f"sg{j}"])
                self.st(Vi("sig", j), 0)

        def trig():
            self.icmp(V("on"), "EQ", 0, self.reset)
            self.iset(V("on"), 1)
            self.set(V("note"), c("nn"))
            self.ld(0, self.c("ivel"))
            p.iconst(12, 0)
            p.float_(0, 0, 12)
            p.st(C["fvel"], 0)
            self.set(V("vel"), c("fvel") * k(LV.INV127))
            self.tword(0, "VLOG2", "ivel")
            self.st(V("vl2"), 0)
            self.set(V("gate"), k(1.0))
            self.fz(V("hp"))
            self.fz(V("lz"))
            self.fz(V("tz"))
            self.fz(V("rise"))
            self.set(V("te"), k(1.0))
            self.set(V("env"), k(1.0))
            self.iset(Vi("quiet"), 0)
            self.iset(c("fresh"), 1)
            self.rt("t_tune", self.tune)
            store_sig()

        def changed():
            self.iset(c("fresh"), 0)
            self.rt("t_tune", self.tune)
            store_sig()
            self.cmp(V("gate"), "EQ", k(0.0), lambda: self.rt("t_damp", self.damp))

        def not_trig():
            self.icmp(V("on"), "NE", 0, lambda: self.icmp(c("chg"), "NE", 0, changed))
        p.ld(0, C["trig"])
        p.ifz(0, "NE", lambda: (self.new_note(), trig()), not_trig)

        def off():
            self.fz(V("gate"))
            self.rt("t_damp", self.damp)
        self.icmp(c("off"), "NE", 0, lambda: self.icmp(V("on"), "NE", 0, lambda: self.cmp(
            V("gate"), "NE", k(0.0), off)))
        self.icmp(V("on"), "EQ", 0, self.zeros, lambda: self.rt("t_render", self.render))

    def ring_base(self, d: int) -> None:
        """Rd = this slot's ring (THOLET_RING_DDR + RING x 4 x t)"""
        p = self.p
        p.ld(9, self.L.t_word)
        p.lsh(d, 9, 16)
        p.iconst(12, self.L.ring)
        p.iop(d, 12, "+", d)

    # -- live.Voice.tune: the 24 partials --------------------------------------------------------------
    def tune(self) -> None:
        p, C = self.p, self.L.C
        V, c, q, e = self.V, self.c, self.q, self.e
        self.set(c("felt"), q("FELT"))
        self.set(c("ep"), q("EP"))
        self.set(c("tone"), q("TONE"))
        self.set(c("dec"), q("DEC"))
        self.set(c("pitch"), V("note") + (e("TUNE") - k(64.0)))
        self.set(c("f0"), k(440.0) * exp2f((c("pitch") - k(69.0)) * k(float(F(F(1.0) / F(12.0))))))
        self.set(V("f0"), c("f0"))
        self.set(c("pm"), c("pitch") - k(60.0))
        self.set(c("bb"), k(0.00015) * exp2f(c("pm") * k(1.0 / 24.0)))
        self.set(c("t60"), (k(0.4) + k(18.0) * (c("dec") * c("dec"))) * exp2f((k(48.0) - c("pitch")) * k(1.0 / 30.0)))
        self.set(V("t60"), c("t60"))
        self.set(c("det"), exp2f((q("STRK") * k(4.0)) * k(1.0 / 1200.0)))
        self.set(c("hard"), (k(0.12) + k(0.35) * (k(1.0) - c("tone"))) + k(1.4) * c("felt"))
        self.set(c("ep1"), k(1.0) - c("ep"))
        # the strike: HAMR's option, its ratio
        self.ev(e("HAMR"), 0)
        p.trunc(0, 0)
        p.iconst(12, 0)
        p.iop(0, 0, "MAX", 12)
        p.iconst(12, LV.NH - 1)
        p.iop(0, 0, "MIN", 12)
        self.st(self.Vi("hk"), 0)
        p.st(C["hki"], 0)
        self.tword(0, "HINV", "hki")
        p.st(C["hinv"], 0)
        self.set(V("hr"), c("f0") * c("hinv"))
        self.set(V("ed"), expf((-k(LN60)) * (k(DT) * recip(c("t60")))))
        # the partials: I3 = the resonator's record, I1 its row
        self.vaddr("rr", "res")
        p.iconst(0, self.L.tables + 4 * TAB["PART"][0])
        p.st(C["pr"], 0)
        p.iconst(0, 0)
        p.st(C["pi"], 0)
        p.iconst(0, NR)
        p.st(C["cnt2"], 0)

        def one():
            self.ptr(3, "rr")
            self.ptr(0, "pr")
            R = lambda j: Mv("i", 0, j)                       # noqa: E731  the row's words
            Ri = lambda j: Mv("i", 0, j, isint=True)          # noqa: E731
            S = lambda j: Mv("i", 3, j)                       # noqa: E731  the record's
            self.set(c("dt"), k(1.0))
            p.ld(0, C["pi"])
            p.iconst(12, LV.NP_)
            p.if_(0, "GE", 12, lambda: self.set(c("dt"), c("det")), kind="i")
            self.set(c("fpp"), R(0))
            self.set(c("bn"), c("bb") * (c("fpp") * c("fpp")))
            self.set(c("st"), (k(1.0) + c("bn") * k(0.5)) - (c("bn") * c("bn")) * k(0.125))
            self.set(c("fp"), ((c("fpp") * c("f0")) * c("st")) * c("dt"))
            self.set(c("ap"), (R(2) * expf((-c("hard")) * R(1))) * exp2f((k(0.5) + k(0.1) * c("fpp")) * V("vl2")))
            self.set(c("tp"), c("t60") * R(3))

            def tine():
                self.set(c("fp"), c("ep1") * c("fp") + c("ep") * ((R(5) * c("f0")) * c("dt")))
                self.set(c("ap"), c("ep1") * c("ap") + c("ep") * R(6))
                self.set(c("tp"), c("ep1") * c("tp") + c("ep") * (c("t60") * R(7)))
            self.icmp(Ri(4), "NE", 0, tine, lambda: self.set(c("ap"), c("ap") * c("ep1")))
            self.set(c("x"), c("fp") * k(DT))

            def zero():
                self.fz(S(2))
                self.fz(S(3))
                self.fz(S(5))

            def live():
                self.cmp(c("tp"), "LE", k(0.02), lambda: self.set(c("tp"), k(0.02)))
                self.set(c("r"), expf((-k(LN60)) * (k(DT) * recip(c("tp")))))
                self.set(S(4), sin_turns(c("x") + k(0.25)))
                self.set(S(2), (k(2.0) * c("r")) * S(4))
                self.set(S(3), -(c("r") * c("r")))
                self.set(S(5), sin_turns(c("x")) * c("ap"))
            self.cmp(c("x"), "LT", k(0.45), live, zero)

            def strike():
                self.set(S(0), S(5))
                self.fz(S(1))
            self.icmp(c("fresh"), "NE", 0, strike)
            self.bump("rr", 4 * RW)
            self.bump("pr", 4 * RROW)
            self.bump("pi", 1)
        self.ivloop("cnt2", one)

    # -- live.Voice.damp ---------------------------------------------------------------------------
    def damp(self) -> None:
        p, C = self.p, self.L.C
        c, q = self.c, self.q
        self.set(c("rq"), q("REL"))
        self.set(c("rel"), k(0.04) + k(1.2) * (c("rq") * c("rq")))
        self.set(c("r"), expf((-k(LN60)) * (k(DT) * recip(c("rel")))))
        self.set(c("rr2"), c("r") * c("r"))
        self.vaddr("rr", "res")
        p.iconst(0, NR)
        p.st(C["cnt2"], 0)

        def one():
            self.ptr(3, "rr")
            S = lambda j: Mv("i", 3, j)                       # noqa: E731
            self.cmp(-S(3), "GT", c("rr2"), lambda: (self.set(S(2), (k(2.0) * c("r")) * S(4)),
                                                    self.set(S(3), -c("rr2"))))
            self.bump("rr", 4 * RW)
        self.ivloop("cnt2", one)

    # -- the three passes --------------------------------------------------------------------------
    def render(self) -> None:
        p, C, L = self.p, self.L.C, self.L
        V, Vi, c, q = self.V, self.Vi, self.c, self.q
        self.set(c("felt"), q("FELT"))
        self.set(c("ep"), q("EP"))
        self.set(c("lev"), q("LEV"))
        self.set(c("gran"), q("GRAN"))
        self.set(c("vs"), q("VSNS"))
        self.set(c("br"), q("BRTH"))
        self.set(c("cf"), k(1.0) - k(0.93) * c("felt"))
        self.cmp(c("cf"), "LE", k(0.05), lambda: self.set(c("cf"), k(0.05)))
        self.set(c("f1"), k(1.0) - c("felt"))
        self.set(c("f6"), c("felt") * k(0.6))
        self.set(c("f25"), c("felt") * k(0.25))
        self.set(c("sg"), ((k(0.55) + k(0.45) * V("vel")) * (k(0.9) - k(0.4) * c("ep")))
                 * ((c("br") * k(127.0 / 64.0)) * k(0.8)))
        self.set(c("bark"), k(0.35) * c("ep"))
        self.set(c("velg"), (k(1.0) - c("vs")) + c("vs") * V("vel"))
        self.set(c("og"), (c("lev") * c("velg")) * k(0.7))
        self.iset(c("cloud"), 0)
        self.cmp(c("gran"), "GT", k(0.0), lambda: self.icmp(Vi("clr"), "EQ", 0, lambda: self.iset(c("cloud"), 1)))

        def cloud_set():
            self.set(c("dq"), q("GDEN"))
            self.set(c("sq"), q("GSIZ"))
            self.set(c("fq"), q("GFM"))
            self.set(c("pq"), q("GSPR"))
            self.set(c("dens"), k(2.0) + k(120.0) * (c("dq") * c("dq")))
            self.set(c("gap"), k(48000.0) * recip(c("dens")))
            self.set(c("gl"), k(48000.0) * (k(0.008) + k(0.052) * c("sq")))
            self.set(c("gdk"), expf(-recip(c("gl") * k(0.22))))
            self.set(c("fm"), (k(3.0) + k(40.0) * c("fq")) * k(DT))
            self.set(c("fmd"), c("fq") * k(0.5))
            self.set(c("spr"), (c("pq") * k(0.33)) * k(48000.0))
            self.set(c("dry"), k(1.0) - k(0.6) * c("gran"))
            self.set(c("sw"), c("gran") * k(1.2))
        self.icmp(c("cloud"), "NE", 0, cloud_set)
        self.fz(c("peak"))
        self.iset(c("bad"), 0)
        self.pass_strike()
        self.pass_strings()
        self.pass_voice()

        def blown():
            self.iset(V("on"), 0)
            self.reset()
            self.zeros()
        self.icmp(c("bad"), "NE", 0, blown, self.rest)

    def rest(self) -> None:
        V, Vi, c = self.V, self.Vi, self.c
        p = self.p

        def count():
            def quiet():
                self.ld(0, Vi("quiet"))
                p.iconst(12, 1)
                p.iop(0, 12, "+", 0)
                self.st(Vi("quiet"), 0)
            self.cmp(c("peak"), "LT", k(LV.REST_AMP), quiet, lambda: self.iset(Vi("quiet"), 0))
            self.icmp(Vi("quiet"), "GE", LV.REST_BLOCKS, lambda: self.iset(V("on"), 0))
        self.cmp(V("gate"), "EQ", k(0.0), count, lambda: self.cmp(V("env"), "LT", k(1e-3), count))

    def pass_strike(self) -> None:
        p, C = self.p, self.L.C
        V, Vi, c = self.V, self.Vi, self.c
        p.iconst(0, self.L.A["sk"])
        p.st(C["skp"], 0)

        def one():
            self.fz(c("s"))

            def read():
                self.floor_int("i0", V("hp"))
                self.set(c("fr"), V("hp") - c("i0f"))
                self.hit_byte("i0", "ha")
                self.bump("i0", 1)
                self.hit_byte("i0", "hb")
                self.set(c("s"), c("ha") + c("fr") * (c("hb") - c("ha")))
                self.set(V("hp"), V("hp") + V("hr"))
            self.cmp(V("hp"), "LT", k(float(LV.HIT_N - 2)), read)
            self.set(V("lz"), V("lz") + c("cf") * (c("s") - V("lz")))
            self.set(c("s"), c("f1") * c("s") + c("f6") * V("lz"))

            def thud():
                self.set(c("nz"), u01() * k(2.0) - k(1.0))
                self.set(V("tz"), V("tz") + k(0.05) * (((c("nz") * V("te")) * c("f25")) - V("tz")))
                self.set(V("te"), V("te") * k(0.998265))
                self.set(c("s"), c("s") + V("tz") * k(4.0))
            self.cmp(V("te"), "GT", k(1e-4), thud)
            self.ptr(4, "skp")
            self.set(Mv("i", 4, 0), c("s") * c("sg"))
            self.bump("skp", 4)
        p.loop(C["cnt0"], BLOCK, one)

    def hit_byte(self, iw: str, dst: str) -> None:
        """c(dst) = MULAW[strike hk's byte C[iw]]"""
        p, C = self.p, self.L.C
        self.ld(0, self.Vi("hk"))
        p.iconst(12, 4 * NHB)
        p.mul_ssi(0, 0, 12)                    # the strike's words, in bytes
        p.ld(13, C[iw])
        p.lsh(12, 13, -2)
        p.lsh(12, 12, 2)
        p.iop(0, 12, "+", 0)                   # + its word's bytes
        p.iconst(12, self.L.tables + 4 * TAB["HITS"][0])
        p.iop(0, 12, "+", 0)
        p.seti(1, 0)
        p.ldi(0, 0, 1)
        p.iconst(12, 3)
        p.iop(13, 13, "AND", 12)
        p.lsh(13, 13, 3)
        p.iconst(12, 0)
        p.iop(13, 12, "-", 13)                 # -(8 (i & 3)): a right shift
        _lsh_by(p, 0, 13)
        p.iconst(12, 0xFF)
        p.iop(0, 0, "AND", 12)
        p.lsh(0, 0, 2)
        p.iconst(12, self.L.tables + 4 * TAB["MULAW"][0])
        p.iop(0, 12, "+", 0)
        p.seti(1, 0)
        p.ldi(0, 0, 1)
        p.st(C[dst], 0)

    def pass_strings(self) -> None:
        p, C = self.p, self.L.C
        c = self.c
        for j in range(BLOCK):
            self.fz(self.a("acs", j))
        self.vaddr("rr", "res")
        p.iconst(0, NR)
        p.st(C["cnt2"], 0)

        def res():
            self.ptr(3, "rr")
            S = lambda j: Mv("i", 3, j)                       # noqa: E731
            self.set(c("c0"), S(2))
            self.set(c("c1"), S(3))
            self.set(c("y1"), S(0))
            self.set(c("y2"), S(1))
            p.iconst(0, self.L.A["acs"])
            p.st(C["ap4"], 0)

            def one():
                self.set(c("y"), c("c0") * c("y1") + c("c1") * c("y2"))
                self.set(c("y2"), c("y1"))
                self.set(c("y1"), c("y"))
                self.ptr(4, "ap4")
                self.set(Mv("i", 4, 0), Mv("i", 4, 0) + c("y"))
                self.bump("ap4", 4)
            p.loop(C["cnt0"], BLOCK, one)
            self.ptr(3, "rr")
            self.set(S(0), c("y1"))
            self.set(S(1), c("y2"))
            self.bump("rr", 4 * RW)
        self.ivloop("cnt2", res)

    def pass_voice(self) -> None:
        p, C, L = self.p, self.L.C, self.L
        V, Vi, c = self.V, self.Vi, self.c
        p.ld(9, L.t_word)
        p.lsh(12, 9, 2)
        p.iconst(11, BUFFERS)
        p.iop(12, 11, "+", 12)
        p.seti(1, 12)
        p.ldi(0, 0, 1)
        p.st(C["outp"], 0)
        p.iconst(0, 0)
        p.st(C["jj"], 0)

        def one():
            self.set(c("acc"), self.jword("acs") * k(0.225))
            self.set(c("acc"), c("acc") + (c("bark") * c("acc")) * c("acc"))
            self.set(V("rise"), V("rise") + k(0.013793) * (k(1.0) - V("rise")))
            self.set(c("y"), self.jword("sk") + c("acc") * V("rise"))
            self.set(V("env"), V("env") * V("ed"))
            self.icmp(c("cloud"), "NE", 0, self.cloud)
            self.set(c("o"), c("y") * c("og"))
            self.ptr(4, "outp")
            self.ld(0, c("o"))
            p.sti(0, 4, 0)
            self.bump("outp", 4)
            self.set(c("pa"), FP_.ab(c("o")))
            self.cmp(c("pa"), "GT", c("peak"), lambda: self.set(c("peak"), c("pa")))
            self.cmp(c("o"), "GT", k(-16.0), lambda: self.cmp(c("o"), "LT", k(16.0), None, lambda: self.iset(c("bad"), 1)),
                     lambda: self.iset(c("bad"), 1))
            self.bump("jj", 1)
        p.loop(C["cnt0"], BLOCK, one)

    def jword(self, arr: str) -> Mv:
        """the array's word jj (I0 set to it)"""
        p, C = self.p, self.L.C
        p.ld(12, C["jj"])
        p.lsh(12, 12, 2)
        p.iconst(13, self.L.A[arr])
        p.iop(12, 13, "+", 12)
        p.seti(0, 12)
        return Mv("i", 0, 0)

    def ring_at(self, iword: str) -> None:
        """I1 = the ring's word (C[iword] & (RING - 1))"""
        p, C = self.p, self.L.C
        self.ring_base(8)
        p.ld(0, C[iword])
        p.iconst(12, RING - 1)
        p.iop(0, 0, "AND", 12)
        p.lsh(0, 0, 2)
        p.iop(0, 8, "+", 0)
        p.seti(1, 0)

    def cloud(self) -> None:
        p, C = self.p, self.L.C
        V, Vi, c = self.V, self.Vi, self.c
        self.set(V("fph"), V("fph") + c("fm"))
        self.cmp(V("fph"), "GE", k(1.0), lambda: self.set(V("fph"), V("fph") - k(1.0)))
        self.ld(0, Vi("wp"))
        p.st(C["wpi"], 0)
        self.ring_at("wpi")
        self.ld(0, c("y"))
        p.sti(0, 1, 0)
        self.fz(c("cl"))
        self.ld(8, Vi("nxt"))
        p.iconst(12, 1)
        p.iop(0, 8, "-", 12)
        self.st(Vi("nxt"), 0)
        self.icmp(Vi("nxt"), "LE", 0, self.spawn)
        # the grains
        self.vaddr("gp", "gr")
        p.iconst(0, NG)
        p.st(C["cnt2"], 0)

        def grain():
            self.ptr(3, "gp")
            G = lambda j: Mv("i", 3, j)                       # noqa: E731
            Gi = Mv("i", 3, 4, isint=True)

            def play():
                self.floor_int("gi", G(0))
                self.set(c("fr"), G(0) - c("gif"))
                self.ring_at("gi")
                self.set(c("ga"), Mv("i", 1, 0))
                self.bump("gi", 1)
                self.ring_at("gi")
                self.set(c("gb"), Mv("i", 1, 0))
                self.ptr(3, "gp")
                self.set(c("cl"), c("cl") + (c("ga") + c("fr") * (c("gb") - c("ga"))) * G(2))
                self.set(G(2), G(2) * G(3))
                self.set(c("pp"), G(0) + G(1))
                self.cmp(c("pp"), "GE", k(float(RING)), lambda: self.set(G(0), c("pp") - k(float(RING))),
                         lambda: self.set(G(0), c("pp")))
                self.ld(8, Gi)
                p.iconst(12, 1)
                p.iop(0, 8, "-", 12)
                self.st(Gi, 0)
            self.icmp(Gi, "GT", 0, play)
            self.bump("gp", 4 * GW)
        self.ivloop("cnt2", grain)
        self.ld(0, Vi("wp"))
        p.iconst(12, 1)
        p.iop(0, 12, "+", 0)
        p.iconst(12, RING - 1)
        p.iop(0, 0, "AND", 12)
        self.st(Vi("wp"), 0)
        self.set(c("y"), c("y") * c("dry") + (c("cl") * c("sw")) * (k(1.0) - V("env")))

    def spawn(self) -> None:
        """the first free grain starts; the next in gap x (0.25 .. 1.75), 64 samples at least"""
        p, C = self.p, self.L.C
        V, Vi, c = self.V, self.Vi, self.c
        self.vaddr("gp", "gr")
        self.iset(c("done"), 0)
        p.iconst(0, NG)
        p.st(C["cnt2"], 0)

        def one():
            self.ptr(3, "gp")
            G = lambda j: Mv("i", 3, j)                       # noqa: E731
            Gi = Mv("i", 3, 4, isint=True)

            def start():
                self.set(c("back"), k(96.0) + u01() * c("spr"))
                self.set(c("rate"), (k(1.0) + c("fmd") * sin_turns(V("fph"))) + (u01() * k(0.04) - k(0.02)))
                self.ld(0, Vi("wp"))
                p.iconst(12, 0)
                p.float_(0, 0, 12)
                p.st(C["wpf"], 0)
                self.set(c("pos"), c("wpf") - c("back"))
                self.ptr(3, "gp")
                self.cmp(c("pos"), "LT", k(0.0), lambda: self.set(G(0), c("pos") + k(float(RING))),
                         lambda: self.set(G(0), c("pos")))
                self.set(G(1), c("rate"))
                self.set(G(2), k(1.0))
                self.set(G(3), c("gdk"))
                self.ev(c("gl"), 0)
                p.trunc(0, 0)
                self.st(Gi, 0)
                self.iset(c("done"), 1)
            self.icmp(c("done"), "EQ", 0, lambda: self.icmp(Gi, "LE", 0, start))
            self.bump("gp", 4 * GW)
        self.ivloop("cnt2", one)
        self.set(c("nx"), c("gap") * (k(0.25) + k(1.5) * u01()))
        self.ev(c("nx"), 0)
        p.trunc(0, 0)
        p.iconst(12, 64)
        p.iop(0, 0, "MAX", 12)
        self.st(Vi("nxt"), 0)


def voice(p, L: Layout, t: int | None = None) -> TG:
    g = TG(p, L)
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
    return Layout(FP_.layout(), dsp.THOLET_TABLES_DDR, dsp.THOLET_RING_DDR)
