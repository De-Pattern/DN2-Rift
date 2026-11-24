"""SPALL (RIFT v0.25, owner 2026-11-24; the MICROCUT concept's v1, claude/microcut-concepts.md): sound
built from tiny, individually shaped events - clicks, dust, short tonal grains, logic chips - scheduled
by a stochastic clock, coloured by six oscillators, and rung through two pingable resonators.

float32 after every operation, Ravel's leaves (organ.live: sin_turns, exp2f, note_hz, recip, xs_bi) and
DIGIDRUM's decay / t60, so the SHARC program can be held to it bit for bit.

**The events.** A trig starts a field: one event at once, then, while DENS > 0, a clock at DENS
(0.25 .. 512 a second) offers an event at each tick; GAP is the chance one is skipped. CLMP makes each
event that sounds the head of a clump: up to seven more follow at sixteen times the rate. MEM (0: free)
is the length, in clock ticks, after which the generator starts again from where the note began, so a
phrase repeats exactly. Each event restarts the particle: a level (0.5 .. 1, the generator's), an
exponential decay of SIZE (0.05 .. 200 ms) and, for the tonal types, the oscillator(s) ALG gives it.

**TYPE** IMP (one impulse), DUST (noise), TONE (the oscillators), CHIP (the sign of one oscillator times
the sign of the next: a pulse's XOR). **ALG** SUM (all six, / 3), RING (one times the next), SCAN (one
oscillator an event, the next event the next). The six run free at the note x (k + 1)^(1 + 1.5 SPRD):
SPRD 0 the harmonic series, up from there stretched and inharmonic.

**The surface.** EDGE softens each event (a one-pole low-pass, 2^-8 .. 1 a sample); two two-pole
resonators (DIGIDRUM's Bp) at FRQA and FRQB (30 Hz .. 15 kHz) ring for RING (5 ms .. 5 s, T60); COUP
feeds A's ring into B. MIX goes from the direct events to the rings; LEV the level, after a soft clip.

Controls (0..127). Page 1 PARTICLES: TYPE SIZE DENS GAP / EDGE CLMP MEM LEV.
Page 2 SURFACE: TUNE SPRD ALG FRQA / FRQB RING COUP MIX.
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, DT, recip, exp2f, sin_turns, note_hz, xs_bi, xs32
from ..digidrum.live import decay, t60, sat

FS = 48000
BLOCK = 32
PAGE1 = ("TYPE", "SIZE", "DENS", "GAP", "EDGE", "CLMP", "MEM", "LEV")
PAGE2 = ("TUNE", "SPRD", "ALG", "FRQA", "FRQB", "RING", "COUP", "MIX")
CONTROLS = PAGE1 + PAGE2
TYPES = ("IMP", "DUST", "TONE", "CHIP")
ALGS = ("SUM", "RING", "SCAN")
DEFAULTS = dict(TYPE=0, SIZE=40, DENS=56, GAP=40, EDGE=90, CLMP=30, MEM=0, LEV=100,
                TUNE=64, SPRD=30, ALG=90, FRQA=60, FRQB=96, RING=60, COUP=20, MIX=80)
INV127 = F(F(1.0) / F(127.0))
INV3 = F(F(1.0) / F(3.0))
HALF = F(0.5)
# log2(k + 1), k = 0..5: the oscillators' ratios are exp2f(LOG2K[k] x (1 + 1.5 SPRD))
LOG2K = tuple(F(np.log2(k + 1)) for k in range(6))
OSC_MAX = F(0.45)                        # an oscillator's step at most (21.6 kHz)
CLUMP_RATE = F(16.0)
RES_GAIN = F(0.25)
OUT_GAIN = F(0.9)
TONE_GAIN = F(0.35)            # the tonal types' particles, against the clicks' full level


def option(k: int, n: int) -> int:
    return min((min(max(int(k), 0), 127) * n) >> 7, n - 1)


def wrap1(x):
    return F(x - F(1.0)) if x >= F(1.0) else x


def sgn(x):
    return F(1.0) if x >= F(0.0) else F(-1.0)


class Res:
    """DIGIDRUM's two-pole resonator, its coefficients set once a block: v = x + c a1 - r^2 a2,
    out v sin(w) RES_GAIN (an impulse rings at about RES_GAIN, whatever its pitch)"""

    def __init__(self):
        self.a1 = self.a2 = F(0.0)
        self.c = self.r2 = self.g = F(0.0)

    def set(self, fc, r):
        w = F(F(fc) * DT)
        self.c = F(F(F(2.0) * F(r)) * sin_turns(F(w + F(0.25))))
        self.r2 = F(F(r) * F(r))
        self.g = F(sin_turns(w) * RES_GAIN)

    def __call__(self, x):
        v = F(F(F(x) + F(self.c * self.a1)) - F(self.r2 * self.a2))
        self.a2, self.a1 = self.a1, v
        return F(v * self.g)


class Voice:
    def __init__(self, slot: int = 0):
        self.on = False
        self.slot = slot
        self.rng = [0x2545F491 + slot]
        self.seed = 0x2545F491 + slot
        self.ph = [F(0.0)] * 6
        self.ra, self.rb = Res(), Res()
        self.clock = self.env = self.lp = F(0.0)
        self.burst = self.ticks = self.scan = F(0.0)
        self.age = F(0.0)
        self.osc = F(0.0)

    # -- the generator: Ravel's xorshift, bipolar; u01 = (bi + 1) / 2
    def bi(self):
        return xs_bi(self.rng)

    def u01(self):
        return F(F(self.bi() + F(1.0)) * HALF)

    def note_on(self):
        self.on = True
        self.seed = self.rng[0]
        self.clock = F(0.0)
        self.burst = self.ticks = F(0.0)
        self.scan = F(0.0)
        self.env = self.lp = F(0.0)
        self.ra.a1 = self.ra.a2 = self.rb.a1 = self.rb.a2 = F(0.0)

    def event(self, size_k):
        """a particle starts: its level and decay; the next oscillator for SCAN"""
        self.env = F(F(F(self.u01() * HALF) + HALF))
        self.ek = size_k
        self.age = F(0.0)
        self.osc = self.scan
        s = F(self.scan + F(1.0))
        self.scan = F(0.0) if s >= F(6.0) else s

    def block(self, k: dict, note: float, trig: bool = False, n: int = BLOCK) -> np.ndarray:
        if trig:
            self.note_on()
        out = np.zeros(n, np.float32)
        if not self.on:
            return out
        q = {c: F(F(k[c]) * INV127) for c in CONTROLS}
        ty = option(k["TYPE"], 4)
        alg = option(k["ALG"], 3)
        size = F(F(0.00005) * exp2f(F(q["SIZE"] * F(12.0))))          # 0.05 .. 205 ms
        size_k = decay(size)
        dens = int(k["DENS"])
        rate = F(F(0.25) * exp2f(F(q["DENS"] * F(11.0))))              # 0.25 .. 512 a second
        ginc = F(rate * DT)
        binc = F(ginc * CLUMP_RATE)
        gap = F(q["GAP"] * F(0.95))
        nclump = F(int(k["CLMP"]) >> 4)                                # 0 .. 7 more
        mem = F(int(k["MEM"]) >> 3)                                    # 0: free, 1 .. 15 ticks
        edge = exp2f(F(F(q["EDGE"] - F(1.0)) * F(8.0)))                # 2^-8 .. 1
        hz = note_hz(F(F(note) + F(F(F(k["TUNE"]) - F(64.0)) * F(0.375))))
        base = F(hz * DT)
        ex = F(F(1.0) + F(q["SPRD"] * F(1.5)))
        inc = [min(F(base * exp2f(F(LOG2K[j] * ex))), OSC_MAX) for j in range(6)]
        fa = F(F(30.0) * exp2f(F(q["FRQA"] * F(9.0))))
        fb = F(F(30.0) * exp2f(F(q["FRQB"] * F(9.0))))
        ring = F(F(0.005) * exp2f(F(q["RING"] * F(10.0))))             # 5 ms .. 5.1 s
        r = t60(ring)
        self.ra.set(fa, r)
        self.rb.set(fb, r)
        coup = F(q["COUP"] * F(0.9))
        mix = q["MIX"]
        dry = F(F(1.0) - mix)
        lev = F(F(q["LEV"] * F(1.27)) * OUT_GAIN)
        if trig:
            self.event(size_k)
        for i in range(n):
            # the clock: an offered event each turn (a clump's own at sixteen times the rate)
            if self.burst > F(0.0):
                self.clock = F(self.clock + binc)
                if self.clock >= F(1.0):
                    self.clock = F(self.clock - F(1.0))
                    self.burst = F(self.burst - F(1.0))
                    self.event(size_k)
            elif dens > 0:
                self.clock = F(self.clock + ginc)
                if self.clock >= F(1.0):
                    self.clock = F(self.clock - F(1.0))
                    if mem > F(0.0):
                        self.ticks = F(self.ticks + F(1.0))
                        if self.ticks >= mem:
                            self.ticks = F(0.0)
                            self.rng[0] = self.seed
                    if self.u01() >= gap:
                        self.event(size_k)
                        self.burst = nclump
            # the oscillators, free
            for j in range(6):
                self.ph[j] = wrap1(F(self.ph[j] + inc[j]))
            # the particle
            if ty == 0:
                x = self.env if self.age == F(0.0) else F(0.0)
            elif ty == 1:
                x = F(self.bi() * self.env)
            else:
                o = int(self.osc)
                o1 = o + 1 if o < 5 else 0
                if ty == 3:
                    s = F(sgn(sin_turns(self.ph[o])) * sgn(sin_turns(self.ph[o1])))
                elif alg == 0:
                    s = F(0.0)
                    for j in range(6):
                        s = F(s + sin_turns(self.ph[j]))
                    s = F(s * INV3)
                elif alg == 1:
                    s = F(sin_turns(self.ph[o]) * sin_turns(self.ph[o1]))
                else:
                    s = sin_turns(self.ph[o])
                x = F(F(s * TONE_GAIN) * self.env)
            self.env = F(self.env * self.ek)
            self.age = F(self.age + F(1.0))
            # EDGE, the rings, the mix
            self.lp = F(self.lp + F(edge * F(x - self.lp)))
            ya = self.ra(self.lp)
            yb = self.rb(F(self.lp + F(coup * ya)))
            y = F(F(dry * self.lp) + F(mix * F(ya + yb)))
            out[i] = F(sat(F(y * lev)) * OUT_GAIN)
        return out


def render(secs: float = 2.0, note: float = 60.0, **kn) -> np.ndarray:
    k = dict(DEFAULTS)
    k.update(kn)
    v = Voice()
    nb = int(secs * FS) // BLOCK
    return np.concatenate([v.block(k, note, trig=(b == 0)) for b in range(nb)])
