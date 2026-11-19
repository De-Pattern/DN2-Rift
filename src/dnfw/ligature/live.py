"""LIGATURE's voice on the SHARC's arithmetic (float32, FASCIA's `recip` for every divide, Ravel's
rv_math.h leaves): the SHARC program's contract (dnfw.ligature.program, bit-exact, test_ligature_program).

LIGATURE (owner, 2026-11-16: "creating one voice from small building blocks ... like the core concept
from BEAD") is WEFT on the Digitone: twelve blocks, each doing one thing to its inputs A and B, wired
into one voice. v1 (RIFT v0.7): the wiring is one of PATCHES (WEFT's factory patches that use the
first palette, rv_weftdef.h); the 24 settings (two a block) are pages 2-4, each an offset from the
patch's own value (64: the patch as WEFT made it), so a PATCH change keeps sounding as designed and a
p-lock moves a setting from there. Page 1: PATCH, TUNE, FINE, LFO1, LFO2, VSNS, DRIV, LEVL.

**The block run.** Each block runs a whole block of 32 samples in turn, 1 to 12, into its own buffer
in the voice. A cord from an earlier block reads this block's samples; a cord from the block itself
or a later one reads what it made the block before (32 samples late, where WEFT is one sample late:
feedback is well-defined and the patch sounds the same however many voices play).

The blocks are rv_weft.c's kernels (wk_*), statement for statement where they are given here, with
their per-step setup (wf_setup) once a block.
"""
from __future__ import annotations

import numpy as np

from ..organ.live import (F, recip, exp2f, expf, sin_turns, tanf, floorf, clampf, note_hz, DT)
from ..fascia.live import INV127

SUB = 32
NB = 12                                   # blocks a patch
INV16 = F(1.0 / 16777216.0)

# -- WEFT's block numbers (rv_weftdef.h's enum, kept so a .weft.json reads the same) ------------
NONE, PHASE, WAVE, SLOPE, CYCLE, SLEW, LP, BP, HP, ADD, MULT, MIX = range(12)
FOLD, COMP, XOR, FLIP, HOLD = 14, 15, 18, 19, 22
SKIN, BAR, SAT, RUNGLER, IMPULSE, CREASE = 26, 27, 32, 50, 69, 70
TYPES = (PHASE, WAVE, SLOPE, CYCLE, SLEW, LP, BP, HP, ADD, MULT, MIX, FOLD, COMP, XOR, FLIP, HOLD,
         SKIN, BAR, SAT, RUNGLER, IMPULSE, CREASE)
TYPE_NAMES = {PHASE: "PHASE", WAVE: "WAVE", SLOPE: "SLOPE", CYCLE: "CYCLE", SLEW: "SLEW", LP: "LP",
              BP: "BP", HP: "HP", ADD: "ADD", MULT: "MULT", MIX: "MIX", FOLD: "FOLD", COMP: "COMP",
              XOR: "XOR", FLIP: "FLIP", HOLD: "HOLD", SKIN: "SKIN", BAR: "BAR", SAT: "SAT",
              RUNGLER: "RUNG", IMPULSE: "IMPLS", CREASE: "CREAS"}
# the sources an input can take besides a block 1-12
S_PITCH, S_GATE, S_TRIG, S_VEL, S_NOISE, S_LFO1, S_LFO2 = 13, 14, 15, 16, 17, 18, 19
NSRC = 20                                 # 0 (nothing), blocks 1..12, the sources 13..19

RATIO = tuple(F(x) for x in (0.25, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 11.0, 13.0, 16.0))
MODES = {SKIN: (1.0, 1.594, 2.136, 2.296, 2.653, 2.918),       # a circular membrane
         BAR: (1.0, 2.756, 5.404, 8.933, 13.344, 18.638)}     # free at both ends
NM = 6
# the modes' powers as constants (no log2 at run time): log2 of each mode's ratio (its first mode's
# ratio being 1) and of k + 1, for powf(rel, -dark 1.2) and powf(k + 1, -dark 1.5)
L2REL = {t: tuple(F(np.log2(max(r, 1.0))) for r in rs) for t, rs in MODES.items()}
L2K = tuple(F(np.log2(k + 1.0)) for k in range(NM))

# -- the patches: WEFT's factory patches on the first palette (rv_weftdef.h wf_presets) -----------
# (type, A, amt A, B, amt B, setting 1, setting 2); OUT; BMOVE (blocks whose B moves setting 2)
PATCHES = (
    ("INIT", ((WAVE, 0, 0, 0, 0, 85, 64), (SLOPE, 0, 0, 0, 0, 4, 70), (LP, 1, 100, 2, 60, 50, 30),
              (MULT, 3, 100, 2, 100, 64, 64)), 4, 0),
    ("SYNC LD", ((PHASE, 0, 0, 0, 0, 2, 64), (PHASE, 7, 12, 1, 100, 3, 70), (WAVE, 2, 100, 0, 0, 85, 64),
                 (SLOPE, 0, 0, 0, 0, 2, 64), (LP, 3, 100, 4, 55, 62, 70), (MULT, 5, 100, 4, 100, 64, 64),
                 (CYCLE, 0, 0, 0, 0, 22, 64)), 6, 0),
    ("DX BELL", ((PHASE, 0, 0, 0, 0, 10, 64), (WAVE, 1, 100, 0, 0, 0, 64), (SLOPE, 0, 0, 0, 0, 0, 52),
                 (MULT, 2, 100, 3, 100, 64, 64), (PHASE, 4, 45, 0, 0, 2, 64), (WAVE, 5, 100, 0, 0, 0, 64),
                 (SLOPE, 0, 0, 0, 0, 0, 92), (MULT, 6, 100, 7, 100, 64, 64)), 8, 0),
    ("PH DIST", ((PHASE, 0, 0, 0, 0, 2, 64), (SLOPE, 0, 0, 0, 0, 2, 58), (WAVE, 1, 100, 2, 45, 0, 30),
                 (SLOPE, 0, 0, 0, 0, 3, 76), (MULT, 3, 100, 4, 100, 64, 64)), 5, 0),
    ("DRONE", ((PHASE, 0, 0, 0, 0, 2, 64), (PHASE, 0, 0, 0, 0, 3, 66), (WAVE, 1, 100, 0, 0, 85, 64),
               (WAVE, 2, 100, 0, 0, 85, 64), (ADD, 3, 100, 4, 100, 64, 44), (CYCLE, 0, 0, 0, 0, 18, 64),
               (BP, 5, 100, 6, 70, 70, 96), (SLEW, S_GATE, 100, 0, 0, 60, 80), (MULT, 7, 100, 8, 100, 64, 64)), 9, 0),
    ("TANGLE", ((PHASE, 0, 0, 0, 0, 2, 64), (WAVE, 1, 100, 6, 60, 40, 64), (FOLD, 2, 100, 5, 50, 70, 64),
                (BP, 3, 100, 5, 40, 72, 80), (CYCLE, 0, 0, 0, 0, 34, 30), (SLEW, 4, 100, 0, 0, 8, 8),
                (SLOPE, 0, 0, 0, 0, 3, 70), (MULT, 4, 100, 7, 100, 64, 64)), 8, 0),
    ("SH BLIP", ((CYCLE, 0, 0, 0, 0, 58, 10), (HOLD, S_NOISE, 100, 1, 100, 24, 0), (PHASE, 2, 30, 0, 0, 4, 64),
                 (WAVE, 3, 100, 0, 0, 20, 64), (SLOPE, 1, 100, 0, 0, 0, 30), (MULT, 4, 100, 5, 100, 64, 64),
                 (MULT, 6, 100, S_GATE, 100, 64, 64)), 7, 0),
    ("TOMSKIN", ((SLOPE, S_TRIG, 100, 0, 0, 0, 12), (SKIN, 1, 100, S_VEL, 80, 64, 30), (SAT, 2, 100, 0, 0, 25, 64)),
     3, 0x2),
    ("PLONK", ((SLOPE, S_TRIG, 100, 0, 0, 0, 22), (MULT, S_NOISE, 100, 1, 100, 64, 90), (BAR, 2, 100, 1, 18, 62, 66),
               (SAT, 3, 100, 0, 0, 20, 64)), 4, 0),
    ("MANGRVE", ((IMPULSE, 0, 0, 0, 0, 50, 64), (FOLD, 1, 100, 0, 0, 40, 64), (SLOPE, 0, 0, 0, 0, 2, 70),
                 (MULT, 2, 100, 3, 100, 64, 64)), 4, 0),
    ("SPLIT", ((IMPULSE, 0, 0, S_LFO1, 40, 26, 40), (FOLD, 1, 100, 0, 0, 25, 64), (SLOPE, 0, 0, 0, 0, 3, 80),
               (MULT, 2, 100, 3, 100, 64, 64)), 4, 0),
    ("CREASE", ((PHASE, 0, 0, 0, 0, 2, 64), (CREASE, 1, 100, 5, 60, 64, 64), (LP, 2, 100, 0, 0, 70, 30),
                (SLOPE, 0, 0, 0, 0, 3, 70), (CYCLE, 0, 0, 0, 0, 20, 64), (MULT, 3, 100, 4, 100, 64, 64)), 6, 0),
    ("BENJOLN", ((CYCLE, 3, 35, 0, 0, 96, 64), (CYCLE, 3, 25, 0, 0, 88, 64), (RUNGLER, 2, 100, 1, 100, 64, 5),
                 (COMP, 1, 100, 2, 100, 100, 64), (LP, 4, 100, 3, 40, 70, 100), (SLEW, S_GATE, 100, 0, 0, 0, 40),
                 (MULT, 5, 100, 6, 100, 64, 64)), 7, 0),
)
NP = len(PATCHES)


def patch_rows(k: int):
    """patch k's 12 rows (type, a, aa, b, ab, d1, d2), the empty ones (0, ...)"""
    name, blks, out, bm = PATCHES[k]
    rows = [tuple(b) for b in blks] + [(NONE, 0, 0, 0, 0, 0, 0)] * (NB - len(blks))
    return rows, out, bm


for _name, _b, _o, _m in PATCHES:
    assert len(_b) <= NB and 1 <= _o <= len(_b) and all(t in TYPES for t, *_r in _b), _name
    assert sum(1 for t, *_r in _b if t in MODES) <= 2, _name          # two modal bodies a patch at most

# -- the panel ----------------------------------------------------------------------------------
PAGE1 = ("PATCH", "TUNE", "FINE", "LFO1", "LFO2", "VSNS", "DRIV", "LEVL")
SETTINGS = tuple(f"S{i // 2 + 1}{'AB'[i % 2]}" for i in range(2 * NB))
CONTROLS = PAGE1 + SETTINGS
assert len(CONTROLS) == 32
DEFAULTS = {"PATCH": 0, "TUNE": 64, "FINE": 64, "LFO1": 40, "LFO2": 60, "VSNS": 64, "DRIV": 0, "LEVL": 100,
            **{s: 64 for s in SETTINGS}}

MAGIC = 0x4C494721                        # 'LIG!': the voice's state was written by a strike
REST_AMP = F(1e-4)
TRIM = F(0.6)                             # LIGATURE at FASCIA's level (its output knee tops at 0.67)
REST_BLOCKS = 16                          # the gate shut and this many quiet blocks: the voice rests


# -- v0.12: the wirings you make (owner, 2026-11-19: "just fix the ligature ui so its usable") ----
# Each project keeps WSLOTS wirings; PATCH (0..127) picks one. The ColdFire keeps the project's
# table (csrc/sampler/pools.c's list, its RAM copy) and sends it into the pool's WIRE area in DSP
# DDR (dnfw.sampler.machines.WIRE_AREA): WHDR words (WMAGIC, WVERSION), then WSLOTS x WWORDS.
# A wiring: per block two words, then one: w0 = type | A << 8 | B << 16 | setting 1 << 24;
# w1 = amount A (s8) | amount B (s8) << 8 | setting 2 << 16; last = (OUT - 1) | BMOVE << 8.
# decode() is the contract the DSP keeps: any word reads as a safe wiring (a type not in TYPES
# is no block, an input past NSRC is nothing, OUT past the last block the last), so garbage in
# DDR never reaches a kernel. No table (the magic not there): PATCH picks a factory patch, as
# v0.7..v0.11; the seeded table holds exactly those, so a saved sound sounds the same.
WSLOTS = 128
WWORDS = 2 * NB + 1
WHDR = 2
WMAGIC = 0x5747494C                       # 'LIGW' in memory
WVERSION = 1
WTABLE_WORDS = WHDR + WSLOTS * WWORDS
TYPEMAP = tuple(t if t in TYPES else NONE for t in range(256))


def _s8(x: int) -> int:
    x &= 0xFF
    return x - 256 if x >= 128 else x


def encode(rows, out: int, bm: int) -> list[int]:
    """12 rows (type, a, aa, b, ab, d1, d2), OUT (1..12), BMOVE -> WWORDS words"""
    rows = list(rows) + [(NONE, 0, 0, 0, 0, 0, 0)] * (NB - len(rows))
    w = []
    for (ty, sa, aa, sb, ab, d1, d2) in rows:
        w.append((ty & 0xFF) | (sa & 0xFF) << 8 | (sb & 0xFF) << 16 | (int(d1) & 0xFF) << 24)
        w.append((aa & 0xFF) | (ab & 0xFF) << 8 | (int(d2) & 0xFF) << 16)
    w.append(((out - 1) & 0xFF) | (bm & 0xFFF) << 8)
    return w


def decode(words) -> tuple[list, int, int]:
    """WWORDS words -> (rows, OUT 1..12, BMOVE), every field made safe (the DSP's reading)"""
    rows = []
    for i in range(NB):
        w0, w1 = int(words[2 * i]) & 0xFFFFFFFF, int(words[2 * i + 1]) & 0xFFFFFFFF
        sa, sb = (w0 >> 8) & 0xFF, (w0 >> 16) & 0xFF
        rows.append((TYPEMAP[w0 & 0xFF], sa if sa < NSRC else 0, _s8(w1), sb if sb < NSRC else 0,
                     _s8(w1 >> 8), (w0 >> 24) & 0xFF, (w1 >> 16) & 0xFF))
    last = int(words[2 * NB]) & 0xFFFFFFFF
    return rows, min(last & 0xFF, NB - 1) + 1, (last >> 8) & 0xFFF


def seed_table() -> list[int]:
    """a new project's table: slot k holds the factory patch PATCH k always played"""
    out = [WMAGIC, WVERSION]
    for k in range(WSLOTS):
        rows, o, bm = patch_rows(patch_of(k))
        out += encode(rows, o, bm)
    return out


def table_ok(table) -> bool:
    return table is not None and len(table) >= WTABLE_WORDS and int(table[0]) & 0xFFFFFFFF == WMAGIC


def patch_of(k) -> int:
    """PATCH's knob (0..127) -> the patch: equal spans of 0..127, as every choice"""
    return min((int(min(max(int(k), 0), 127)) * NP) >> 7, NP - 1)


def WC(x):
    return F(F(x * F(127.0 / 64.0)) - F(1.0))


def WG(x):
    return F(x * F(127.0 / 64.0))


def WN(x, n):
    v = int(np.int32(np.trunc(F(F(x * F(127.0)) + F(0.5)))))
    return 0 if v < 0 else (n - 1 if v > n - 1 else v)


def wtime(x):
    return F(F(0.0005) * exp2f(F(x * F(14.0))))


def wk(T):
    T = T if T > F(1e-5) else F(1e-5)
    return F(F(1.0) - expf(F(F(-DT) * recip(T))))


def sat(x):
    if x > F(3.0):
        return F(1.0)
    if x < F(-3.0):
        return F(-1.0)
    x2 = F(x * x)
    return F(F(x * F(F(27.0) + x2)) * recip(F(F(27.0) + F(F(9.0) * x2))))


def wwrap(p):
    if p >= F(1.0):
        p = F(p - F(1.0))
        if p >= F(1.0):
            p = F(p - floorf(p))
    elif p < F(0.0):
        p = F(p + F(1.0))
        if p < F(0.0):
            p = F(p - floorf(p))
    return p


def shape_k(k, p):
    if k == 0:
        return sin_turns(p)
    if k == 1:
        if p < F(0.25):
            return F(F(4.0) * p)
        if p < F(0.75):
            return F(F(2.0) - F(F(4.0) * p))
        return F(F(F(4.0) * p) - F(4.0))
    if k == 2:
        return F(F(F(2.0) * p) - F(1.0))
    return F(1.0) if p < F(0.5) else F(-1.0)


def xs32(x):
    """xorshift32 (13, 17, 5): FASCIA's _xs_body (a seed is never 0)"""
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= x >> 17
    x ^= (x << 5) & 0xFFFFFFFF
    return x, x


def xs_uni(rng):
    rng[0], v = xs32(rng[0])
    return F(F(v >> 8) * INV16)


class Block:
    __slots__ = ("ph", "y", "st", "prev", "prevb", "s1", "s2", "hold", "z", "g2", "d2")

    def __init__(self):
        self.ph = self.y = self.prev = self.prevb = self.s1 = self.s2 = self.hold = F(0.0)
        self.g2 = self.d2 = F(0.0)
        self.st = 0
        self.z = [F(0.0)] * (2 * NM)


def rise(x, prev, thr):
    """wrise: a rising edge through THR (-> edge, the new prev)"""
    return (x > thr and prev <= thr), x


class Voice:
    """one slot's LIGATURE voice: note(), off(), block() -> 32 samples"""

    def __init__(self, seed: int):
        self.seed = seed & 0xFFFFFFFF or 1
        self.rng = [self.seed]               # NOISE's dice
        self.rng2 = [self.seed ^ 0x5BD1E995 or 1]   # the RUNGLERs' (one for the voice)
        self.on = False
        self.gate = F(0.0)
        self.trig = False
        self.note_n = F(60.0)
        self.vel = F(1.0)
        self.quiet = 0
        self.lfo = [F(0.0), F(0.0)]
        self.blk = [Block() for _ in range(NB)]
        self.buf = np.zeros((NB, SUB), np.float32)          # each block's last 32 samples
        self.last_patch = -1
        self.table = None                    # v0.12: the WIRE area's words as the DSP sees them

    def reset(self):
        self.blk = [Block() for _ in range(NB)]
        self.buf[:] = 0.0

    def note(self, note, vel):
        if not self.on:
            self.reset()
        self.on = True
        self.trig = True
        self.gate = F(1.0)
        self.note_n = F(note)
        self.vel = F(vel)
        self.quiet = 0

    def off(self):
        self.gate = F(0.0)

    # -- one block of 32 samples --------------------------------------------------------------------
    def block(self, knobs) -> np.ndarray:
        kn = [int(k) for k in knobs]
        out = np.zeros(SUB, np.float32)
        # the LFOs move whether a note plays or not (a sine each, 0.05 .. 25 Hz)
        for q in range(2):
            hzq = F(F(0.05) * exp2f(F(F(F(kn[3 + q]) * INV127) * F(9.0))))
            self.lfo[q] = wwrap(F(self.lfo[q] + F(F(hzq * DT) * F(SUB))))
        if not self.on:
            self.trig = False
            return out
        k0 = min(max(int(kn[0]), 0), 127)
        if table_ok(self.table):             # v0.12: the project's wiring k0
            pk = k0
            rows, outb, bm = decode(self.table[WHDR + WWORDS * k0: WHDR + WWORDS * (k0 + 1)])
        else:                                # none sent yet: the factory patch, as before
            pk = 256 + patch_of(k0)
            rows, outb, bm = patch_rows(patch_of(k0))
        if pk != self.last_patch:            # a new wiring starts clean (WEFT's preset load)
            if self.last_patch >= 0:
                self.reset()
            self.last_patch = pk
        tune = F(F(F(F(kn[1]) - F(64.0)) * F(24.0 / 63.0)))
        fine = F(F(F(kn[2]) - F(64.0)) * F(50.0 / 63.0))
        nn = F(F(self.note_n + tune) + F(fine * F(0.01)))
        hz = note_hz(nn)
        hz = hz if hz < F(12000.0) else F(12000.0)
        # the sources, a block's worth each
        src = np.zeros((NSRC, SUB), np.float32)
        src[S_PITCH, :] = F(F(F(self.note_n + tune) - F(60.0)) * F(1.0 / 48.0))
        src[S_GATE, :] = self.gate
        src[S_TRIG, 0] = F(1.0) if self.trig else F(0.0)
        src[S_VEL, :] = self.vel
        for j in range(SUB):
            src[S_NOISE, j] = F(F(xs_uni(self.rng) * F(2.0)) - F(1.0))
        src[S_LFO1, :] = sin_turns(self.lfo[0])
        src[S_LFO2, :] = sin_turns(self.lfo[1])
        trg = src[S_TRIG]
        gatev = self.gate

        def inp(s):
            if 1 <= s <= NB:
                return self.buf[s - 1]
            return src[s]

        for i, (ty, sa, aa, sb, ab, d1, d2) in enumerate(rows):
            if ty == NONE:
                continue
            S = self.blk[i]
            x1 = F(clampf(F(F(F(d1) + F(F(kn[8 + 2 * i]) - F(64.0))) * INV127), F(0.0), F(1.0)))
            x2 = F(clampf(F(F(F(d2) + F(F(kn[9 + 2 * i]) - F(64.0))) * INV127), F(0.0), F(1.0)))
            moves = (bm >> i) & 1
            pa = inp(sa).copy()
            pb = inp(sb).copy()
            ka = F(F(aa) * F(0.01))
            kb = F(F(ab) * F(0.01))
            ac = sa != 0
            bc = sb != 0 and not moves
            if moves and sb:                 # B MOVES: B (its first sample) on setting 2, once a block
                x2 = F(clampf(F(x2 + F(pb[0] * kb)), F(0.0), F(1.0)))
            if not bc:
                kb = F(0.0)
            yo = np.zeros(SUB, np.float32)
            self._run(ty, S, x1, x2, pa, ka, pb, kb, ac, bc, trg, gatev, hz, yo)
            self.buf[i, :] = yo
        y = self.buf[outb - 1]
        # the voice's level: VSNS (velocity on the level), DRIV (into a soft clip), LEVL
        vs = F(F(kn[5]) * INV127)
        lv = F(F(F(kn[7]) * INV127) * F(F(F(1.0) - vs) + F(vs * self.vel)))
        dr = F(F(1.0) + F(F(F(kn[6]) * INV127) * F(7.0)))
        ok = True
        peak = F(0.0)
        for j in range(SUB):
            v = F(y[j])
            if not (v > F(-16.0) and v < F(16.0)):
                ok = False
                break
            o = F(F(sat(F(v * dr)) * lv) * TRIM)
            out[j] = o
            a = o if o >= F(0.0) else F(-o)
            peak = a if a > peak else peak
        if not ok:                           # a block blew up: the voice rests (FASCIA's fault test)
            self.on = False
            self.reset()
            self.trig = False
            return np.zeros(SUB, np.float32)
        self.trig = False
        if self.gate == F(0.0):
            self.quiet = self.quiet + 1 if peak < REST_AMP else 0
            if self.quiet >= REST_BLOCKS:
                self.on = False
        return out

    # -- the kernels (rv_weft.c wk_*) ------------------------------------------------------------
    def _run(self, ty, S, x1, x2, pa, ka, pb, kb, ac, bc, trg, gatev, hz, yo):
        if ty == PHASE:
            c1 = F(F(F(hz * RATIO[WN(x1, 16)]) * exp2f(F(WC(x2) * F(1.0 / 12.0)))) * DT)
            ph = S.ph
            for j in range(SUB):
                a = F(pa[j] * ka)
                ph = F(ph + F(c1 * F(F(1.0) + F(F(8.0) * a))))
                ph = wwrap(ph)
                if bc:
                    e, S.prevb = rise(F(pb[j] * kb), S.prevb, F(0.0))
                    if e:
                        ph = F(0.0)
                yo[j] = F(F(ph * F(2.0)) - F(1.0))
            S.ph = ph
        elif ty == WAVE:
            k = clampf(F(F(0.5) + F(WC(x2) * F(0.5))), F(0.03), F(0.97))
            rk = F(F(0.5) * recip(k))
            rk1 = F(F(0.5) * recip(F(F(1.0) - k)))
            s3 = F(x1 * F(3.0))
            seg = int(np.int32(np.trunc(s3)))
            seg = 2 if seg > 2 else seg
            fr = F(s3 - F(seg))
            inc = F(hz * DT)
            ph = S.ph
            for j in range(SUB):
                if ac:
                    p = F(F(F(pa[j] * ka) * F(0.5)) + F(0.5))
                else:
                    ph = wwrap(F(ph + inc))
                    p = ph
                p = F(p + F(F(pb[j] * kb) * F(0.5)))
                p = wwrap(p)
                p = F(p * rk) if p < k else F(F(0.5) + F(F(p - k) * rk1))
                v = shape_k(seg, p)
                if fr > F(0.0):
                    v = F(v + F(F(shape_k(seg + 1, p) - v) * fr))
                yo[j] = v
            S.ph = ph
        elif ty in (SLOPE, SLEW):
            kr = wk(wtime(x1))
            kf = wk(wtime(x2))
            yv = S.y
            for j in range(SUB):
                sc = exp2f(F(F(F(-pb[j]) * kb) * F(4.0))) if bc else F(1.0)
                if ty == SLOPE:
                    gg = F(pa[j] * ka) if ac else gatev
                    e, S.prev = rise(gg, S.prev, F(0.5))
                    if e or (not ac and trg[j] > F(0.0)):
                        S.st = 1
                    if S.st == 1:
                        yv = F(yv + F(F(F(1.25) - yv) * clampf(F(kr * sc), F(0.0), F(1.0))))
                        if yv >= F(1.0):
                            yv = F(1.0)
                            S.st = 2
                    elif S.st == 2 and gg <= F(0.5):
                        S.st = 0
                    if S.st == 0:
                        yv = F(yv - F(yv * clampf(F(kf * sc), F(0.0), F(1.0))))
                else:
                    r = F(pa[j] * ka)
                    kk = kr if r > yv else kf
                    yv = F(yv + F(F(r - yv) * clampf(F(kk * sc), F(0.0), F(1.0))))
                yo[j] = yv
            S.y = yv
        elif ty == CYCLE:
            c1 = F(F(F(0.02) * exp2f(F(x1 * F(17.0)))) * DT)
            k = clampf(x2, F(0.01), F(0.99))
            rk = recip(k)
            rk1 = recip(F(F(1.0) - k))
            ph = S.ph
            for j in range(SUB):
                inc = F(c1 * exp2f(F(F(pa[j] * ka) * F(5.0)))) if ac else c1
                ph = wwrap(F(ph + inc))
                if bc:
                    e, S.prevb = rise(F(pb[j] * kb), S.prevb, F(0.0))
                    if e:
                        ph = F(0.0)
                v = F(ph * rk) if ph < k else F(F(F(1.0) - ph) * rk1)
                yo[j] = F(F(v * F(2.0)) - F(1.0))
            S.ph = ph
        elif ty in (LP, BP, HP):
            c1 = F(F(20.0) * exp2f(F(x1 * F(10.0))))
            R = F(F(F(2.0) - F(F(1.96) * x2)) * F(0.5))
            R2 = F(F(2.0) * R)
            g = tanf(F(F(F(3.14159265) * clampf(c1, F(20.0), F(18000.0))) * DT))
            d = recip(F(F(F(1.0) + F(F(R2) * g)) + F(g * g)))
            s1, s2 = S.s1, S.s2
            for j in range(SUB):
                a = F(pa[j] * ka)
                gg, dd = g, d
                if bc:
                    if not (j & 3):
                        b = F(pb[j] * kb)
                        S.g2 = tanf(F(F(F(3.14159265) * clampf(F(c1 * exp2f(F(b * F(5.0)))), F(20.0), F(18000.0))) * DT))
                        S.d2 = recip(F(F(F(1.0) + F(R2 * S.g2)) + F(S.g2 * S.g2)))
                    gg, dd = S.g2, S.d2
                hp = F(F(F(a - F(F(R2 + gg) * s1)) - s2) * dd)
                bp = F(F(gg * hp) + s1)
                s1 = F(F(gg * hp) + bp)
                lp = F(F(gg * bp) + s2)
                s2 = F(F(gg * bp) + lp)
                y = lp if ty == LP else (F(bp * R2) if ty == BP else hp)
                if not (y > F(-8.0) and y < F(8.0)):
                    s1 = s2 = y = F(0.0)
                yo[j] = y
            S.s1, S.s2 = s1, s2
        elif ty in (ADD, MULT, MIX):
            o = F(WC(x1) * F(2.0))
            gn = WG(x2)
            for j in range(SUB):
                a = F(pa[j] * ka)
                b = F(pb[j] * kb)
                if ty == ADD:
                    yo[j] = F(F(F(a + b) + o) * gn)
                elif ty == MULT:
                    yo[j] = F(F(a * F((b if bc else F(1.0)) + o)) * gn)
                else:
                    yo[j] = F(F(a + F(F(b - a) * x1)) * gn)
        elif ty == FOLD:
            dr = F(F(1.0) + F(x1 * F(15.0)))
            o = WC(x2)
            for j in range(SUB):
                a = F(pa[j] * ka)
                b = F(pb[j] * kb)
                yo[j] = sin_turns(F(F(F(F(a * dr) * F(F(1.0) + b)) + o) * F(0.25)))
        elif ty in (COMP, XOR, FLIP):
            thr = WC(x2)
            for j in range(SUB):
                a = F(pa[j] * ka)
                b = F(pb[j] * kb)
                if ty == COMP:
                    r = a > F(b + thr)
                elif ty == XOR:
                    r = (a > thr) != (b > thr)
                else:
                    e, S.prev = rise(a, S.prev, thr)
                    if e:
                        S.st ^= 1
                    if bc:
                        e, S.prevb = rise(b, S.prevb, thr)
                        if e:
                            S.st = 0
                    r = S.st == 1
                yo[j] = x1 if r else F(-x1)
        elif ty == HOLD:
            kh = wk(wtime(F(x2 * F(0.8)))) if x2 > F(0.0) else F(1.0)
            lv = F(F(2.0) + F(x1 * F(30.0)))
            rl = recip(lv)
            for j in range(SUB):
                if bc:
                    e, S.prevb = rise(F(pb[j] * kb), S.prevb, F(0.0))
                else:
                    e = trg[j] > F(0.0)
                if e:
                    qv = F(pa[j] * ka)
                    if x1 > F(0.0):
                        qv = F(F(F(floorf(F(F(F(F(qv * F(0.5)) + F(0.5)) * lv) + F(0.5))) * rl) * F(2.0)) - F(1.0))
                    S.hold = qv
                S.y = F(S.y + F(F(S.hold - S.y) * kh))
                yo[j] = S.y
        elif ty in (SKIN, BAR):
            pm = F(pb[0] * kb) if bc else F(0.0)
            base = F(hz * exp2f(pm))
            dark = F(F(1.0) - x2)
            T0 = F(F(0.002) * exp2f(F(x1 * F(12.0))))
            cs = []
            for k in range(NM):
                f = F(base * F(MODES[ty][k]))
                T = F(T0 * exp2f(F(F(F(-dark) * F(1.2)) * L2REL[ty][k])))
                r = expf(F(F(F(-6.9078) * DT) * recip(T)))
                gk = F(exp2f(F(F(F(-dark) * F(1.5)) * L2K[k])) * F(0.5))
                x = F(f * DT)
                if x > F(0.45) or x <= F(0.0):
                    cs.append((F(0.0), F(0.0), F(0.0)))
                else:
                    cs.append((F(F(F(2.0) * r) * sin_turns(F(x + F(0.25)))), F(-F(r * r)), F(sin_turns(x) * gk)))
            acc = np.zeros(SUB, np.float32)
            ain = (pa * ka).astype(np.float32)
            z = list(S.z)
            for k in range(NM):
                c0, c1_, c2 = cs[k]
                y0, y1 = z[2 * k], z[2 * k + 1]
                for j in range(SUB):
                    yk = F(F(F(c0 * y0) + F(c1_ * y1)) + F(c2 * F(ain[j])))
                    y1 = y0
                    y0 = yk
                    acc[j] = F(acc[j] + yk)
                z[2 * k], z[2 * k + 1] = y0, y1
            if all(F(-16.0) < acc[j] < F(16.0) for j in range(SUB)):
                S.z = z
                yo[:] = acc
            else:                            # blown up: the body starts over, silent this block
                S.z = [F(0.0)] * (2 * NM)
                yo[:] = 0.0
        elif ty == SAT:
            dr = F(F(1.0) + F(x1 * F(15.0)))
            o = WC(x2)
            for j in range(SUB):
                a = F(pa[j] * ka)
                m = exp2f(F(F(pb[j] * kb) * F(2.0))) if bc else F(1.0)
                yo[j] = sat(F(F(F(F(a * dr) * m) + o) * F(0.8)))
        elif ty == IMPULSE:
            d = F(F(F(0.02) * exp2f(F(F(-x1) * F(9.0)))) * F(48000.0))
            r = clampf(F(F(1.0) - x2), F(0.01), F(1.0))
            if bc:
                d = F(d * exp2f(F(F(-clampf(F(pb[0] * kb), F(-1.0), F(1.0))) * F(3.0))))
            d = d if d > F(2.0) else F(2.0)
            rd = F(r * d)
            up = F(F(2.0) * recip(rd if rd > F(1.0) else F(1.0)))
            rd1 = F(F(F(1.0) - r) * d)
            dn = F(2.0) if r >= F(1.0) else F(F(2.0) * recip(rd1 if rd1 > F(1.0) else F(1.0)))
            ph, lv, st = S.ph, S.y, S.st
            if st > 2 or not (lv == lv) or abs(lv) > F(1.0):
                st, lv = 0, F(-1.0)
            inc = F(hz * DT)
            for j in range(SUB):
                if ac:
                    t, S.prev = rise(F(pa[j] * ka), S.prev, F(0.0))
                else:
                    ph = F(ph + inc)
                    t = ph >= F(1.0)
                    if t:
                        ph = F(ph - floorf(ph))
                if t and st != 1:
                    st = 1
                if st == 1:
                    lv = F(lv + up)
                    if lv >= F(1.0):
                        lv, st = F(1.0), 2
                elif st == 2:
                    lv = F(lv - dn)
                    if lv <= F(-1.0):
                        lv, st = F(-1.0), 0
                yo[j] = lv
            S.ph, S.y, S.st = ph, lv, st
        elif ty == CREASE:
            sh = WG(x1)
            o = WC(x2)
            for j in range(SUB):
                y = F(F(F(pa[j] * ka) + F(pb[j] * kb)) + o)
                yo[j] = F(y + sh) if y < F(0.0) else F(y - sh)
        elif ty == RUNGLER:
            L = 3 + WN(x2, 6)
            mask = (1 << L) - 1
            for j in range(SUB):
                if ac:
                    e, S.prev = rise(F(pa[j] * ka), S.prev, F(0.0))
                else:
                    e = trg[j] > F(0.0)
                if e:
                    last = (S.st >> (L - 1)) & 1
                    if bc:
                        nb = 1 if F(pb[j] * kb) > F(0.0) else 0
                    else:
                        nb = 1 if xs_uni(self.rng2) < F(0.5) else 0
                    keep = F(xs_uni(self.rng2) * F(0.999)) < x1
                    S.st = ((S.st << 1) | (last if keep else nb)) & mask
                yo[j] = F(F(F((S.st >> (L - 3)) & 7) * F(2.0 / 7.0)) - F(1.0))
        else:
            raise ValueError(ty)


def slot_seed(slot: int) -> int:
    return (0x6C696700 + 0x01000193 * (slot + 1)) & 0xFFFFFFFF


class SlotVoice(Voice):
    """the voice as the DN2 drives it, a block at a time: the 32 knobs, the trig, its note and
    velocity (0..127), the note-off (mask 36)"""

    def __init__(self, slot: int):
        super().__init__(slot_seed(slot))
        self.slot = slot

    def dsp_block(self, knobs, trig: bool, note: float, vel: int, off: bool) -> np.ndarray:
        if trig:
            self.note(note, F(min(int(vel), 127)) * INV127)
        if off:
            self.off()
        return self.block(knobs)


def render(knobs, notes, seconds: float, slot: int = 0) -> np.ndarray:
    """an audition: NOTES = [(time s, note, vel, length s)], the knobs fixed"""
    v = SlotVoice(slot)
    nblk = int(seconds * 48000) // SUB
    ev = sorted(notes)
    out = []
    for b in range(nblk):
        t0, t1 = b * SUB / 48000.0, (b + 1) * SUB / 48000.0
        trig = None
        off = False
        for (t, n, vel, ln) in ev:
            if t0 <= t < t1:
                trig = (n, vel)
            if t0 <= t + ln < t1:
                off = True
        if trig:
            out.append(v.dsp_block(knobs, True, trig[0], trig[1], off and False))
        else:
            out.append(v.dsp_block(knobs, False, 60, 100, off))
    return np.concatenate(out) if out else np.zeros(0, np.float32)
