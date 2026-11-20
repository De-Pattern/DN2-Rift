"""smear.asm: SMEAR's stage in the DSP's chain (docs/smear.md, "The chain").

smp.asm handles a SMEAR track (type 9, WERP's) as it handles every sample machine up to the
render: the trigger, the slot latched at a note (its base, frames, rate and format, checked
against the pool), the note's pitch. Instead of rendering, it leaves the track a MAILBOX
(`glue`, below) and jumps on here. This stage then, for each track whose mailbox is on:
- takes a VOC lane at a note (two lanes for the whole instrument: a free one, else the
  one taken longest ago);
- writes the voice's inputs (program.VLayout) and runs one voice block
  (program.emit_voice, a subroutine: one copy of the code);
- copies the 32 samples into the track's buffer, as FASCIA does.
A lane whose owner left (its mailbox not seen this block) is freed. The block clock moves on,
and the stage jumps on to fascia.asm.

At its first block after power-on it computes the transform's twiddles and the window from the
quarter sine (fft.emit_init; about 196k instructions, once).

The contract is `run_blocks` (the same rules in Python over live.Voice), held bit for bit by
test/test_smear_stage.py.
"""
from __future__ import annotations

import struct

import numpy as np

from ..perc.dsl import Mem, Prog
from . import fft as FT
from . import live as LV
from . import program as P

# the mailbox smp.asm leaves a track (words)
MB_ON, MB_TRIG, MB_TR, MB_RATE, MB_BASE, MB_FRAMES, MB_FMT, MB_KN = 0, 1, 2, 3, 4, 5, 6, 7
MB_WORDS = 32                              # 7 + 12 knobs, rounded up
STATE_BYTES = 512                          # a voice's state in DDR (program.VLayout.STATE_WORDS words, rounded)
INIT_MAGIC = 0x534D5249                    # 'SMRI': the tables computed this power-on
NTRACKS = 16


class SLayout:
    """INIT must be a word the image loads as zero (the power-on block runs when it is not
    INIT_MAGIC). Where the stage's words, the mailboxes, the voices' states and the lanes are.

    SCR: the stage's own words (fixed); MBOX: 16 mailboxes; STATE: 16 voice states (DDR);
    V: the voice's layout (program.VLayout); TABLES: the transform's tables (QSIN's image
    copy, the pairs, then what emit_init computes); BUFFERS: the track buffers' pointers."""

    def __init__(self, scr: int, mbox: int, state: int, vbase: int, tables: int, vtables: int,
                 qsin: int, lanes: tuple, buffers: int, clears: tuple = ()):
        self.INIT, self.CLOCK, self.T, self.SEEN, self.LOWN0, self.LOWN1, self.LAGE0, self.LAGE1, self.CNT = (
            scr + 4 * k for k in range(9))
        self.scr_end = scr + 64
        self.MBOX, self.STATE, self.QSIN, self.BUFFERS = mbox, state, qsin, buffers
        self.V = P.VLayout(vbase, tables, vtables, lanes)
        self.tables = tables
        self.clears = clears                    # (address, bytes): zeroed at power-on (FASCIA's voices)

    def mb(self, t: int, w: int) -> int:
        return self.MBOX + 4 * (MB_WORDS * t + w)


def _mb_addr(p: Prog, S: SLayout, d: int, w: int) -> None:
    """Rd = the address of word W of track T's mailbox (T in S.T); clobbers R12."""
    p.ld(d, S.T)
    p.lsh(d, d, 7)                              # 32 words, 128 bytes a mailbox
    p.iconst(12, S.MBOX + 4 * w)
    p.iop(d, 12, "+", d)


def _lane_of(p: Prog, S: SLayout, d: int) -> None:
    """Rd = the lane track T holds (0, 1) or -1; clobbers R12, R13."""
    p.ld(13, S.T)
    p.iconst(12, 1)
    p.iop(13, 13, "+", 12)                      # t + 1
    p.iconst(d, -1)
    p.ld(12, S.LOWN1)
    p.if_(12, "EQ", 13, lambda: p.iconst(d, 1), kind="i")
    p.ld(12, S.LOWN0)
    p.if_(12, "EQ", 13, lambda: p.iconst(d, 0), kind="i")


def _take_lane(p: Prog, S: SLayout) -> None:
    """A note on track T (it holds no lane): a free lane, else the one taken longest ago."""
    p.ld(0, S.T)
    p.iconst(12, 1)
    p.iop(0, 12, "+", 0)                        # t + 1
    p.ld(1, S.CLOCK)

    def take0():
        p.st(S.LOWN0, 0)
        p.st(S.LAGE0, 1)

    def take1():
        p.st(S.LOWN1, 0)
        p.st(S.LAGE1, 1)

    def not0():
        p.ld(2, S.LOWN1)

        def oldest():                           # both held: the older (LAGE0 <= LAGE1: lane 0)
            p.ld(2, S.LAGE0)
            p.ld(3, S.LAGE1)
            p.e("COMP(R2, R3);")
            p._branch(lambda: _s32(p.r[2]) <= _s32(p.r[3]), "LE", take0, take1)
        p.ifz(2, "EQ", take1, oldest)
    p.ld(2, S.LOWN0)
    p.ifz(2, "EQ", take0, not0)


def _s32(x: int) -> int:
    x &= 0xFFFFFFFF
    return x - (1 << 32) if x & 0x80000000 else x


def _track(p: Prog, S: SLayout) -> None:
    """track T: its mailbox on -> its voice's block into its buffer."""
    V = S.V
    _mb_addr(p, S, 4, MB_ON)
    p.seti(4, 4, "track t's mailbox")
    p.ldi(0, MB_ON, 4)

    def on():
        p.iconst(0, 0)
        p.sti(MB_ON, 4, 0)                      # consumed
        p.ld(0, S.SEEN)                         # the owners seen this block (bit t)
        p.iconst(1, 1)
        p.ld(9, S.T)
        _shl_by(p, 1, 9)
        p.iop(0, 0, "OR", 1)
        p.st(S.SEEN, 0)
        # the inputs
        for k in range(12):
            p.ldi(0, MB_KN + k, 4)
            p.st(V.KN0 + 4 * k, 0)
        for w, mw in (("TR", MB_TR), ("RATE", MB_RATE), ("TRIG", MB_TRIG), ("SIZE", MB_FRAMES),
                      ("BASE", MB_BASE), ("FMT", MB_FMT)):
            p.ldi(0, mw, 4)
            p.st(getattr(V, w), 0)
        p.ld(0, S.CLOCK)
        p.st(V.CLOCK, 0)
        p.ldi(0, MB_TRIG, 4)
        p.ldi(1, MB_FRAMES, 4)                  # (an empty slot takes no lane)
        p.ifz(1, "LE", lambda: p.iconst(0, 0))
        p.ifz(0, "NE", lambda: (_lane_of(p, S, 0), p.ifz(0, "LT", lambda: _take_lane(p, S))))
        _lane_of(p, S, 0)
        p.st(V.LANE, 0)
        p.ld(0, S.T)
        p.lsh(0, 0, 9)                          # STATE_BYTES a voice
        p.iconst(12, S.STATE)
        p.iop(0, 12, "+", 0)
        p.st(V.VSTATE, 0)
        # an empty slot (no frames): silence, the voice left as it is
        p.ldi(0, MB_FRAMES, 4)

        def play():
            P.emit_voice(p, V)              # once: the track loop runs it
        p.ifz(0, "GT", play, lambda: _zero_out(p, V))
        # the track's buffer
        p.ld(9, S.T)
        p.lsh(12, 9, 2)
        p.iconst(11, S.BUFFERS)
        p.iop(12, 11, "+", 12)
        p.seti(1, 12)
        p.ldi(0, 0, 1)
        p.seti(4, 0, "the track's buffer")
        p.iconst(9, V.OUT)
        p.seti(1, 9)

        def cp():
            p.ldpost(0, 1)
            p.stpost(4, 0)
        p.loop_r(15, 32, cp)
    p.ifz(0, "NE", on)


def _zero_out(p: Prog, V) -> None:
    p.iconst(9, V.OUT)
    p.seti(1, 9)
    p.iconst(0, 0)
    p.loop_r(15, 32, lambda: p.stpost(1, 0))


def _shl_by(p: Prog, d: int, n: int) -> None:
    """Rd <<= Rn (0..15): a loop of single shifts, as perc's _shift_by."""
    from ..perc import program as PP
    PP._shift_by(p, d, n)


def stage(p: Prog, S: SLayout) -> None:
    """one block of the stage (no entry label, no jump on). The power-on block only computes
    the tables and clears the mailboxes (DDR and L2 hold anything at power-on: a mailbox is
    trusted only once cleared), so the first block after power-on is silent."""
    done = p.label("smrdone")
    p.ld(0, S.INIT)
    p.iconst(1, INIT_MAGIC)

    def init():
        FT.emit_init(p, S.QSIN, FT.tabs(S.V.L.FFT), S.V.L.WIN)
        # RIFT v0.16: the image no longer loads FASCIA's voices' zeros (63 KB of the DSP's 1 MiB):
        # they are cleared here, at the first block after each load (INIT is a loaded zero),
        # before fascia.asm's first walk
        for at, n in S.clears:
            p.iconst(0, 0)
            p.iconst(9, at)
            p.seti(1, 9)
            p.loop_r(15, n // 4, lambda: p.stpost(1, 0))
        p.iconst(0, 0)
        for w in (S.CLOCK, S.LOWN0, S.LOWN1, S.LAGE0, S.LAGE1):
            p.st(w, 0)
        p.iconst(9, S.MBOX)
        p.seti(1, 9)
        p.loop_r(15, NTRACKS * MB_WORDS, lambda: p.stpost(1, 0))
        p.iconst(1, INIT_MAGIC)
        p.st(S.INIT, 1)
        if not p.run:
            p.jump("", done)
    if p.run and (p.mem.get(S.INIT) or 0) != INIT_MAGIC:
        init()
        return
    p.if_(0, "NE", 1, init, kind="i")
    p.iconst(0, 0)
    p.st(S.SEEN, 0)
    p.st(S.T, 0)
    p.loop(S.CNT, NTRACKS, lambda: (_track(p, S), p.ld(9, S.T), p.iconst(12, 1), p.iop(0, 12, "+", 9),
                                     p.st(S.T, 0)))
    # lanes whose owner was not seen: free
    p.ld(3, S.SEEN)
    for own in (S.LOWN0, S.LOWN1):
        p.ld(0, own)

        def held(own=own):
            p.iconst(12, -1)
            p.iop(9, 12, "+", 0)                # t
            p.ipass(1, 3)
            _shr_by(p, 1, 9)
            p.iconst(12, 1)
            p.iop(1, 1, "AND", 12)
            p.ifz(1, "EQ", lambda: (p.iconst(2, 0), p.st(own, 2)))
        p.ifz(0, "NE", held)
    p.ld(9, S.CLOCK)
    p.iconst(12, 1)
    p.iop(0, 12, "+", 9)
    p.st(S.CLOCK, 0)
    p.place(done)


def _shr_by(p: Prog, d: int, n: int) -> None:
    """Rd >>= Rn (logical, 0..15): a loop of single shifts."""
    if p.run:
        p.r[d] = (p.r[d] & 0xFFFFFFFF) >> (p.r[n] & 31)
        p.e("shr")
        return
    top, done = p.label("shr"), p.label("shrd")
    p.ipass(13, n)
    p.place(top)
    p.e("R13 = PASS R13;")
    p.jump("EQ", done)
    p.e(f"R{d} = LSHIFT R{d} BY -1;")
    p.iconst(12, -1)
    p.iop(13, 13, "+", 12)
    p.jump("", top)
    p.place(done)


def program(S: SLayout, next_sw: int, prefix: str = "smr") -> str:
    """smear.asm: entered by smp.asm's tail; on to NEXT_SW (fascia.asm) when done."""
    p = Prog("emit", prefix=prefix)
    p.raw("// smear.asm -- SMEAR, the granular, phase-vocoded looper (docs/smear.md), type 9.")
    p.raw("// GENERATED by scripts/gen_smear_asm.py from dnfw.smear; do not edit by hand.")
    p.raw("")
    p.raw(".SECTION/PM seg_pmco;")
    p.raw("")
    p.raw(".GLOBAL wr_smr.;")
    p.raw("wr_smr.:")
    stage(p, S)
    p.e(f"JUMP {next_sw:#x};", "fascia.asm's wr_fsc")
    p.emit_subs()
    p.raw(".wr_smr..end:")
    return "\n".join(p.lines) + "\n"


# ---------------------------------------------------------------------------- the contract
class Model:
    """the stage's rules over live.Voice: the lanes, the clock, the mailboxes' inputs"""

    def __init__(self):
        self.clock = 0
        self.own = [0, 0]
        self.age = [0, 0]
        self.voices: dict[int, LV.Voice] = {}

    def _lane(self, t):
        if self.own[0] == t + 1:
            return 0
        if self.own[1] == t + 1:
            return 1
        return None

    def block(self, mail: dict) -> dict:
        """MAIL: {t: (buf float32 array, rate, tr, trig, knobs dict)} -> {t: 32 samples}"""
        out, seen = {}, 0
        for t in range(NTRACKS):
            if t not in mail:
                continue
            buf, rate, tr, trig, kn = mail[t]
            seen |= 1 << t
            if trig and len(buf) and self._lane(t) is None:
                if self.own[0] == 0:
                    self.own[0], self.age[0] = t + 1, self.clock
                elif self.own[1] == 0:
                    self.own[1], self.age[1] = t + 1, self.clock
                elif self.age[0] <= self.age[1]:
                    self.own[0], self.age[0] = t + 1, self.clock
                else:
                    self.own[1], self.age[1] = t + 1, self.clock
            lane = self._lane(t)
            if len(buf) == 0:
                out[t] = np.zeros(32, np.float32)
                continue
            v = self.voices.get(t)
            if v is None or v.buf is not buf:
                v = self.voices[t] = LV.Voice(buf, rate)
            out[t] = v.block(kn, tr, trig, self.clock, lane)
        for k in range(2):
            if self.own[k] and not (seen >> (self.own[k] - 1)) & 1:
                self.own[k] = 0
        self.clock += 1
        return out


def u32(x) -> int:
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def load_tables(mem: Mem, S: SLayout) -> None:
    """what the image holds: the quarter sine, the pairs, the voice's tables"""
    for k, w in enumerate(qsin_words()):
        mem.put(S.QSIN + 4 * k, w)
    for k, w in enumerate(pairs_words()):
        mem.put(FT.tabs(S.V.L.FFT).pairs + 4 * k, w)
    for k, w in enumerate(P.voice_tables_words()):
        mem.put(S.V.VT + 4 * k, w)


def qsin_words() -> list[int]:
    return [u32(x) for x in FT.QSIN]


def pairs_words() -> list[int]:
    return FT.tables_words()[:FT.T_TWF // 4]
