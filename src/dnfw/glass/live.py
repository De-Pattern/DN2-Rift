"""GLASS's filter on the SHARC's arithmetic (RIFT v0.18: a new FLTR type after the Serge VCFQ, on every
machine; the reference model, the owner's auditions of 2026-11-21: `dnfw.fx.glass`).

Float32 after every operation, Ravel's leaves (organ.live: recip, exp2f, expf, sin_turns, note_hz), no
tan, pow, sqrt or division. The SHARC program (program.py) is held to this bit for bit.

**Where it runs.** On the DSP, a FLTR type the stock unpack does not know reaches the per-track chain
as "no filter" (DSP filter 0: docs/ping.md, measured), so the chain skips its filter stage. GLASS
filters the slot's buffer in place after every machine has rendered (at FASCIA's walk's end), before
that chain's gain, base/width filter and amp. Its settings are the stock filter fields the unpack writes
into the track record as floats (Multi-Mode's page, its records):

| record | stock | GLASS |
|---|---|---|
| `+0x1c8` | TYPE (0..1) | the morph: LP (0), BP (0.5), HP (1) |
| `+0x1cc` | FREQ (0..1) | the cutoff, x 128 = a note number |
| `+0x1d0` | RESO (0..1) | the ring's time: 4 ms .. 4 s at every pitch |
| `+0x1ec` | env delay | LPG: OFF under 0.5, ON from 0.5 |
| `+0x1f0` | env attack | ATK, 0.1 ms .. 400 ms |
| `+0x1f4` | env decay | DEC, 2 ms .. 10 s |
| `+0x1f8` | env sustain | ATK BEND: 0 exponential, 0.5 straight, 1 logarithmic |
| `+0x1fc` | env release | DEC BEND: the same |
| `+0x204` | env depth (0.5 = 0) | ENV, +-6 octaves on the cutoff |
| `+0x208` | key tracking | how far the cutoff follows the note from C4 |

**The differences from the reference, for the DSP's cost:** the coefficients and the envelope are
set once a block (32 samples, 0.67 ms), the level (LPG) ramped across it; the soft limit inside the loop
is a quadratic knee (exactly linear below KNEE, bounded at 2 KNEE: no square root); RES's curve is
r (0.7 + 0.3 r) for r^1.3. The envelope is attack-decay from each trig, its two segments bent.
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, recip, exp2f, expf, sin_turns, note_hz

FS = 48000
SUB = 32
FILTER_TYPE = 6                       # the ColdFire's filter type (the FLTR list's seventh)
R_TYPE, R_FREQ, R_RES = 0x1C8, 0x1CC, 0x1D0
R_LPG, R_ATK, R_DEC, R_ABND, R_DBND = 0x1EC, 0x1F0, 0x1F4, 0x1F8, 0x1FC
R_DEPTH, R_KEYT = 0x204, 0x208
FIELDS = (R_TYPE, R_FREQ, R_RES, R_LPG, R_ATK, R_DEC, R_ABND, R_DBND, R_DEPTH, R_KEYT)

KNEE = F(1.2)                         # the loop's limit: linear below, rounded to 2 KNEE above
KNEE3 = F(F(3.0) * KNEE)
KNEE2 = F(F(2.0) * KNEE)
INV4K = F(F(1.0) / F(F(4.0) * KNEE))
PI_2FS = F(F(3.14159265358979) / F(F(2.0) * F(48000.0)))   # tan's argument at twice the rate, a turn
INV_PI = F(0.318309886)
DT = F(F(1.0) / F(48000.0))
BLK = F(F(32.0) / F(48000.0))         # a block's seconds
TWOPI_FS = F(F(6.28318530717958647692) * DT)
SQRT2 = F(1.41421356)
INV_SUB = F(F(1.0) / F(32.0))
F_MAX = F(20000.0)
F_MIN = F(16.0)
LPG_STEP = F(0.25)                    # the vactrol's rise: a quarter of the way a block (about 2.3 ms)


def knee(x):
    """linear below KNEE; |x| in KNEE..3 KNEE: |x| - (|x| - KNEE)^2 / (4 KNEE); above: 2 KNEE"""
    x = F(x)
    a = F(abs(x))
    if a <= KNEE:
        return x
    if a >= KNEE3:
        return KNEE2 if x > F(0.0) else F(F(0.0) - KNEE2)
    d = F(a - KNEE)
    y = F(a - F(F(d * d) * INV4K))
    return y if x > F(0.0) else F(F(0.0) - y)


def bend(u, b):
    """a segment 0..1 at U, bent by B (0 exponential: slow then fast; 0.5 straight; 1 logarithmic):
    k = 12 |B - 0.5|; below 0.5 (e^(k u) - 1) / (e^k - 1), above its mirror 1 - that at 1 - u"""
    u = F(u)
    c = F(F(b) - F(0.5))
    if F(abs(c)) < F(0.004):
        return u
    k = F(F(12.0) * F(abs(c)))
    den = recip(F(expf(k) - F(1.0)))
    if c < F(0.0):
        return F(F(expf(F(k * u)) - F(1.0)) * den)
    return F(F(1.0) - F(F(expf(F(k * F(F(1.0) - u))) - F(1.0)) * den))


class Voice:
    """GLASS on one slot"""

    def __init__(self):
        self.s1 = self.s2 = self.lowz = F(0.0)
        self.stage = 0                    # 0 off, 1 attack, 2 decay
        self.u = F(0.0)                   # the segment's position 0..1
        self.env = F(0.0)
        self.vac = F(0.0)                 # LPG's vactrol, 0..1
        self.vtarget = F(0.0)

    def block(self, rec: dict, trig: bool, nn, x: np.ndarray) -> np.ndarray:
        """REC: the record's floats by offset (FIELDS); NN the note; X the slot's 32 samples -> 32"""
        typ, freq, res = F(rec[R_TYPE]), F(rec[R_FREQ]), F(rec[R_RES])
        lpg = rec[R_LPG] >= F(0.5)
        # the envelope: a trig starts the attack; once a block, then bent
        if trig:
            self.stage = 1
            self.u = F(0.0)
            self.vtarget = F(1.0)
        atk = F(F(0.0001) * exp2f(F(F(rec[R_ATK]) * F(12.0))))
        dec = F(F(0.002) * exp2f(F(F(rec[R_DEC]) * F(12.3))))
        if self.stage == 1:
            self.u = F(self.u + F(BLK * recip(atk)))
            if self.u >= F(1.0):
                self.stage, self.u, self.env = 2, F(0.0), F(1.0)
            else:
                self.env = bend(self.u, rec[R_ABND])
        elif self.stage == 2:
            self.u = F(self.u + F(BLK * recip(dec)))
            if self.u >= F(1.0):
                self.stage, self.u, self.env = 0, F(0.0), F(0.0)
            else:
                self.env = F(F(1.0) - bend(self.u, rec[R_DBND]))
        else:
            self.env = F(0.0)
        # LPG's vactrol: a fast rise to the trig's 1, then a fall that slows as it closes (DEC sets it)
        v0 = self.vac
        if lpg:
            if self.vtarget > self.vac:
                self.vac = F(self.vac + F(LPG_STEP * F(self.vtarget - self.vac)))   # (about 2.3 ms)
                if self.vac > F(F(0.98) * self.vtarget):
                    self.vtarget = F(0.0)
            else:
                cl = F(F(1.0) - self.vac)
                tau = F(dec * F(F(0.15) + F(F(0.85) * F(cl * cl))))
                self.vac = F(self.vac * expf(F(F(0.0) - F(BLK * recip(tau)))))
        else:
            self.vac = F(1.0)
            self.vtarget = F(0.0)
        # the cutoff (a note number): FREQ, key tracking, the envelope, the LPG's opening
        note = F(F(freq * F(128.0)) + F(F(rec[R_KEYT]) * F(nn - F(60.0))))
        note = F(note + F(F(F(F(rec[R_DEPTH]) - F(0.5)) * F(144.0)) * self.env))
        if lpg:
            note = F(F(20.0) + F(F(note - F(20.0)) * self.vac))
        hz = note_hz(note)
        hz = F(min(max(hz, F_MIN), F_MAX))
        # tan(pi f / 2fs) as sin / cos (turns)
        w = F(hz * F(PI_2FS * INV_PI * F(0.5)))
        g = F(sin_turns(w) * recip(sin_turns(F(w + F(0.25)))))
        # RES: the ring's time constant 4 ms .. 4 s (r^1.3 as r (0.7 + 0.3 r)); Q = pi f tau, >= 0.5
        rs = F(res * F(F(0.7) + F(F(0.3) * res)))
        tau = F(F(0.004) * exp2f(F(rs * F(9.96578428))))
        q = F(max(F(F(F(3.14159265) * hz) * tau), F(0.5)))
        k = recip(q)
        a1 = recip(F(F(1.0) + F(g * F(g + k))))
        drive = F(F(1.0) - F(F(0.45) * F(res * res)))
        idrive = recip(drive)
        lp1 = F(F(1.0) - expf(F(F(0.0) - F(TWOPI_FS * hz))))
        keep = F(F(0.5) * res)
        if res < F(0.3):
            keep = F(keep * F(res * F(1.0 / 0.3)))
        kb = F(k * SQRT2)
        lev0 = v0 if lpg else F(1.0)
        lev1 = self.vac if lpg else F(1.0)
        dlev = F(F(lev1 - lev0) * INV_SUB)
        lev = lev0
        y = np.zeros(SUB, np.float32)
        for i in range(SUB):
            xi = F(x[i])
            xin = F(xi * drive)
            lp = bp = hp = F(0.0)
            for _ in range(2):
                v3 = F(xin - self.s2)
                v1 = F(a1 * F(self.s1 + F(g * v3)))
                v2 = F(self.s2 + F(g * v1))
                self.s1 = knee(F(F(F(2.0) * v1) - self.s1))
                self.s2 = F(F(F(2.0) * v2) - self.s2)
                lp, bp = v2, v1
                hp = F(F(xin - F(k * v1)) - v2)
            lp = F(lp * idrive)
            bp = F(bp * idrive)
            hp = F(hp * idrive)
            self.lowz = F(self.lowz + F(lp1 * F(xi - self.lowz)))
            lp = F(lp + F(keep * F(self.lowz - lp)))
            if typ <= F(0.5):
                t = F(typ * F(2.0))
                o = F(F(F(F(1.0) - t) * lp) + F(t * F(bp * kb)))
            else:
                t = F(F(typ - F(0.5)) * F(2.0))
                o = F(F(F(F(1.0) - t) * F(bp * kb)) + F(t * hp))
            y[i] = F(o * lev)
            lev = F(lev + dlev)
        return y
