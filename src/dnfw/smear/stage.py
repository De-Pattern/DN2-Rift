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
MB_MAGIC = 0x534D4F4E                      # 'SMON' in MB_ON: written by smp.asm this block (anything else: off)
STATE_BYTES = 512                          # a voice's state in DDR (program.VLayout.STATE_WORDS words, rounded)
INIT_MAGIC = 0x534D5249                    # 'SMRI': the tables computed this power-on
INIT_BUSY = 0x534D5242                     # 'SMRB': the tables being computed, a part a block (ISTEP the next)
NTRACKS = 16


class SLayout:
    """INIT must be a word the image loads as zero (the power-on block runs when it is not
    INIT_MAGIC). Where the stage's words, the mailboxes, the voices' states and the lanes are.

    SCR: the stage's own words (fixed); MBOX: 16 mailboxes; STATE: 16 voice states (DDR);
    V: the voice's layout (program.VLayout); TABLES: the transform's tables (QSIN's image
    copy, the pairs, then what emit_init computes); BUFFERS: the track buffers' pointers."""

    def __init__(self, scr: int, mbox: int, state: int, vbase: int, tables: int, vtables: int,
                 qsin: int, lanes: tuple, buffers: int, clears: tuple = (), pairs: int | None = None,
                 ready: int | None = None, cost: int | None = None, smp_pos: int | None = None):
        self.INIT, self.CLOCK, self.T, self.SEEN, self.LOWN0, self.LOWN1, self.LAGE0, self.LAGE1, self.CNT = (
            scr + 4 * k for k in range(9))
        self.ISTEP = scr + 36                   # the power-on work's next part (while INIT is INIT_BUSY)
        self.LSAVE = scr + 40                   # L0, L3, L5 as found (3 words)
        self.scr_end = scr + 64
        self.MBOX, self.STATE, self.QSIN, self.BUFFERS = mbox, state, qsin, buffers
        n = 4 * P.N                             # WIN at TABLES, then the transform's tables; PAIRS apart (loaded)
        fft = FT.Tabs(pairs if pairs is not None else tables + n + FT.T_PAIRS, tables + n + FT.T_TWF,
                      tables + n + FT.T_TWI, tables + n + FT.T_TWS)
        self.V = P.VLayout(vbase, tables, vtables, lanes, fft=fft)
        self.READY = ready                      # RIFT v0.16: the tables are in once this word is TABLE_MAGIC
        self.COST = cost                        # 16 words: each track's last cost (the guard), or None
        self.SMP_POS = smp_pos                  # RIFT v0.19: the sample voices' states (their "pos" gets the read point), or None
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
    p.iconst(1, MB_MAGIC)

    def on():
        p.iconst(0, 0)
        p.sti(MB_ON, 4, 0)                      # consumed
        p.ld(0, S.INIT)                         # (before the power-on block: silence, below)
        p.iconst(1, INIT_MAGIC)
        p.if_(0, "NE", 1, lambda: (p.iconst(2, 0), p.sti(MB_FRAMES, 4, 2)), kind="i")   # (R0 holds INIT: not it)
        p.ld(0, S.SEEN)                         # the owners seen this block (bit t)
        p.iconst(1, 1)
        p.ld(9, S.T)
        _shl_by(p, 1, 9)
        p.iop(0, 0, "OR", 1)
        p.st(S.SEEN, 0)
        # the inputs
        for k in range(len(LV.CONTROLS)):
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
        if LV.VOC_ON:
            p.ifz(0, "NE", lambda: (_lane_of(p, S, 0), p.ifz(0, "LT", lambda: _take_lane(p, S))))
            _lane_of(p, S, 0)
        else:                                   # RIFT v0.26: no lanes without the FFT vocoder (the DSP's 1 MiB)
            p.iconst(0, -1)
        p.st(V.LANE, 0)
        p.ld(0, S.T)
        p.lsh(0, 0, 9)                          # STATE_BYTES a voice
        p.iconst(12, S.STATE)
        p.iop(0, 12, "+", 0)
        p.st(V.VSTATE, 0)
        # an empty slot (no frames): silence, the voice left as it is
        p.ldi(0, MB_FRAMES, 4)

        def play():
            if S.COST is None or p.run:         # (the model: the voice always runs)
                P.emit_voice(p, V)              # once: the track loop runs it
                return
            # RIFT v0.16: the guard, as every voice of ours: the voice only if it fits the frame
            # (its last cost, eased, against the limit); else silence this block, its state kept
            from ..perc import guard as G
            skip, done = p.label("smrskip"), p.label("smrok")
            p.e("R8 = EMUCLK;")
            p.st(G.START, 8)
            p.ld(9, G.MARK0)
            p.e("R8 = R8 - R9;", "how far into the frame")
            p.ld(9, S.T)
            p.lsh(9, 9, 2)
            p.iconst(10, S.COST)
            p.iop(9, 10, "+", 9)
            p.seti(5, 9)
            p.ldi(9, 0, 5, "this track's last cost")
            p.iconst(10, 0)
            p.iop(9, 9, "MAX", 10)
            p.iconst(10, G.COST_CAP)
            p.iop(9, 9, "MIN", 10)
            p.lsh(10, 9, -1)
            p.iop(9, 10, "+", 9)                # x 1.5
            # RIFT v0.28 (franny: "Smear also seems to drop out pretty easily"): at least SMR_FLOOR only on the
            # block that triggers the track (the frame's trigger word, bit 16 + t), G.IDLE_FLOOR on any other;
            # v0.16..v0.27 asked 60,000 of every block (a SMEAR voice costs 21,000 to 27,000, rprof)
            from ..perc import program as PPg
            p.ld(10, PPg.TRIG_WORD)
            p.lsh(10, 10, -16)
            p.ld(11, S.T)
            p.iconst(12, 1)
            p.e("R12 = LSHIFT R12 BY R11;")
            p.iop(10, 10, "AND", 12)
            p.iconst(11, G.IDLE_FLOOR)
            p.ifz(10, "NE", lambda: p.iconst(11, SMR_FLOOR))
            p.iop(9, 9, "MAX", 11)
            # RIFT v0.18 (the owner's unit: a VOC note, a burst, then silence until a reboot): a voice
            # holding a VOC lane is expected to cost VOC's measured peak, whatever its last block
            # cost. Its light blocks (the hop's other jobs) no longer hide the heavy ones, so a VOC
            # job that does not fit is left out, never run past the frame
            if LV.VOC_ON:                           # RIFT v0.26: not for the keyframe stretch (a few thousand cycles)
                P._tab(p, 10, V, "VG", "BLND")        # VOC heard (its gain > 0) ...

                def lane_held():                    # ... and a lane held: VOC runs this block
                    p.ld(10, V.LANE)
                    p.ifz(10, "GE", lambda: (p.iconst(10, VOC_PEAK), p.iop(9, 9, "MAX", 10)))
                p.ifz(10, "GT", lane_held, kind="f")
            p.iop(8, 8, "+", 9)
            p.ld(10, G.LIMIT)
            p.e("COMP(R8, R10);")
            p.jump("GT", skip)
            P.emit_voice(p, V)
            p.e("R8 = EMUCLK;")
            p.ld(9, G.START)
            p.e("R8 = R8 - R9;", "what the voice cost")
            p.ld(9, S.T)
            p.lsh(9, 9, 2)
            p.iconst(10, S.COST)
            p.iop(9, 10, "+", 9)
            p.seti(5, 9)
            p.sti(0, 5, 8)
            p.jump("", done)
            p.place(skip)
            p.ldi(9, 0, 5)                      # its expected cost eased by a quarter: tried again
            p.lsh(10, 9, -2)
            p.e("R9 = R9 - R10;")
            p.sti(0, 5, 9)
            p.ld(8, G.SKIPS)
            p.iconst(9, 1)
            p.iop(8, 8, "+", 9)
            p.st(G.SKIPS, 8)
            _zero_out(p, V)
            p.place(done)
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
        # RIFT v0.19 (owner: a granular display on SMEAR's page): the read point to the sample
        # machines' voice state's "pos" (what the idle packet sends the ColdFire as the playhead),
        # so the page draws SMEAR's own playhead and its grain cloud around it
        if S.SMP_POS is not None:
            from ..sampler import program as _SPg
            p.ld(9, S.T)
            p.lsh(9, 9, 7)                          # 128 bytes a voice
            p.iconst(12, S.SMP_POS + 4 * _SPg.V["pos"])
            p.iop(9, 12, "+", 9)
            p.seti(1, 9)
            p.ld(0, V.PI)
            p.sti(0, 1, 0)
    p.if_(0, "EQ", 1, on, kind="i")


# RIFT v0.18: a VOC lane's worst block on the unit, cycles: instructions + 0.95 x (4 L2 + 10 DDR)
# accesses, measured in the runner over a hop (scripts/sharc_waverider_m5.py step smrcost holds it)
SMR_FLOOR = 40_000                 # RIFT v0.28: a SMEAR voice's least cost on its trigger block
VOC_PEAK = 270_000


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
    """one block of the stage (no entry label, no jump on). The power-on block computes the
    tables (once the ColdFire's are in: READY); until then every SMEAR track is silence. A
    mailbox is on only when smp.asm wrote MB_MAGIC this block (L2 holds anything at power-on)."""
    from ..sampler import machines as SM
    p.ld(0, S.INIT)
    p.iconst(1, INIT_MAGIC)

    def init():
        def go():
            # RIFT v0.16: a part a block (FT.INIT_PARTS), so no block carries all of it. INIT
            # reads INIT_BUSY while it goes (ISTEP its next part: L2 holds anything at power-on,
            # so ISTEP counts only once INIT says so)
            p.ld(0, S.INIT)
            p.iconst(1, INIT_BUSY)
            p.if_(0, "NE", 1, lambda: (p.iconst(2, 0), p.st(S.ISTEP, 2), p.iconst(2, INIT_BUSY),
                                       p.st(S.INIT, 2)), kind="i")
            if not LV.VOC_ON:                   # RIFT v0.20: VOC off: no transform tables to compute
                last()
                return
            for k in range(FT.INIT_PARTS - 1):
                p.ld(0, S.ISTEP)
                p.iconst(1, k)
                p.if_(0, "EQ", 1, lambda k=k: FT.emit_init(p, S.QSIN, S.V.L.FFT, S.V.L.WIN, part=k), kind="i")
            p.ld(0, S.ISTEP)
            p.iconst(12, 1)
            p.iop(2, 12, "+", 0)
            p.st(S.ISTEP, 2)
            p.iconst(1, FT.INIT_PARTS - 1)
            p.if_(0, "EQ", 1, last, kind="i")

        def last():
            if LV.VOC_ON:
                FT.emit_init(p, S.QSIN, S.V.L.FFT, S.V.L.WIN, part=FT.INIT_PARTS - 1)
            for at, n in S.clears:
                p.iconst(0, 0)
                p.iconst(9, at)
                p.seti(1, 9)
                p.loop_r(15, n // 4, lambda: p.stpost(1, 0))
            p.iconst(0, 0)
            for w in (S.CLOCK, S.LOWN0, S.LOWN1, S.LAGE0, S.LAGE1):
                p.st(w, 0)
            p.iconst(1, INIT_MAGIC)
            p.st(S.INIT, 1)
        if S.READY is None:
            go()
            return
        p.ld(2, S.READY)
        p.iconst(3, SM.TABLE_MAGIC)
        p.if_(2, "EQ", 3, go, kind="i")
    p.if_(0, "NE", 1, init, kind="i")
    p.iconst(0, 0)
    p.st(S.SEEN, 0)
    p.st(S.T, 0)
    p.loop(S.CNT, NTRACKS, lambda: (_track(p, S), p.ld(9, S.T), p.iconst(12, 1), p.iop(0, 12, "+", 9),
                                     p.st(S.T, 0)))
    # lanes whose owner was not seen: free
    p.ld(3, S.SEEN)
    for own in ((S.LOWN0, S.LOWN1) if LV.VOC_ON else ()):
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
    # SMEAR's code post-modifies I0, I3 and I5 (the chain's other programs only pre-modify
    # them): their L registers are made 0 for it (no circular buffer), and given back after
    for k, r in enumerate(("L0", "L3", "L5")):
        p.e(f"DM({S.LSAVE + 4 * k:#x}) = {r};", "as found")
        p.e(f"{r} = 0;")
    stage(p, S)
    for k, r in enumerate(("L0", "L3", "L5")):
        p.e(f"{r} = DM({S.LSAVE + 4 * k:#x});", "given back")
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
            if LV.VOC_ON and trig and len(buf) and self._lane(t) is None:   # RIFT v0.26: no lanes without it
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
        mem.put(S.V.L.FFT.pairs + 4 * k, w)
    for k, w in enumerate(P.voice_tables_words()):
        mem.put(S.V.VT + 4 * k, w)


def qsin_words() -> list[int]:
    return [u32(x) for x in FT.QSIN]


def pairs_words() -> list[int]:
    return FT.tables_words()[:FT.T_TWF // 4]
