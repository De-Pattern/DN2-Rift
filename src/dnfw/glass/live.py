"""RUBBER (RIFT v0.24, the owner 2026-11-24: "replace glass with a RUBBER roland sh-101 style filter ... mono
basslines sound liquid and rubbery"): the FLTR type 6 (GLASS's place, v0.18..v0.23), on every machine.

A four-pole low-pass after the SH-101's IR3109: four one-pole stages, solved with zero-delay feedback (the
loop's instantaneous part solved each sample, so it stays in tune and stable to self-oscillation), the
transistor pair's soft saturation where the chip has it (the input and the resonance loop: Pade's tanh,
DIGIDRUM's `sat`), and a resonance that thins the bass only gently (part of it made up at the input).
The cutoff is ramped across each block (the stages' coefficient interpolated), so a fast envelope sweeps
smoothly: the squelch.

Float32 after every operation, Ravel's leaves (organ.live: recip, exp2f, expf, sin_turns, note_hz), no
tan, pow, sqrt or division. The SHARC program (program.py) is held to this bit for bit.

**Where it runs.** As GLASS did: a FLTR type the stock unpack does not know reaches the per-track chain as
"no filter", so the chain skips its filter stage; RUBBER filters the slot's buffer in place after every
machine has rendered (at FASCIA's walk's end). Its settings are the stock filter fields the unpack
writes into the track record as floats (Multi-Mode's page, its records):

| record | stock | RUBBER |
|---|---|---|
| `+0x1c8` | TYPE (0..1) | DRIVE: the input level into the chip, 1 .. 4 |
| `+0x1cc` | FREQ (0..1) | the cutoff, x 128 = a note number |
| `+0x1d0` | RESO (0..1) | the resonance, to self-oscillation at the top |
| `+0x1f0` | env attack | ATK, 0.1 ms .. 400 ms |
| `+0x1f4` | env decay | DEC, 2 ms .. 10 s |
| `+0x1f8` | env sustain | ATK BEND (FLTR page 2): 0 exponential, 0.5 straight, 1 logarithmic |
| `+0x1fc` | env release | DEC BEND (FLTR page 2): the same |
| `+0x204` | env depth (0.5 = 0) | ENV, +-6 octaves on the cutoff |
| `+0x208` | key tracking | how far the cutoff follows the note from C4 |
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, recip, exp2f, expf, sin_turns, note_hz

FS = 48000
SUB = 32
FILTER_TYPE = 6                       # the ColdFire's filter type (the FLTR list's seventh)
R_TYPE, R_FREQ, R_RES = 0x1C8, 0x1CC, 0x1D0
R_ATK, R_DEC, R_ABND, R_DBND = 0x1F0, 0x1F4, 0x1F8, 0x1FC
R_DEPTH, R_KEYT = 0x204, 0x208
FIELDS = (R_TYPE, R_FREQ, R_RES, R_ATK, R_DEC, R_ABND, R_DBND, R_DEPTH, R_KEYT)

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
K_MAX = F(4.4)                        # the resonance's loop gain at the top (4: the linear ladder's edge)
COMP = F(0.25)                        # the bass the resonance takes, made up at the input (k COMP)
DRIVE_SPAN = F(3.0)                   # DRIVE 1 .. 4
SAT3 = F(3.0)


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


def sat(x):
    """tanh's stand-in (DIGIDRUM's): x (27 + x^2) / (27 + 9 x^2), +-1 beyond |x| = 3"""
    x = F(x)
    if x >= SAT3:
        return F(1.0)
    if x <= F(-3.0):
        return F(-1.0)
    x2 = F(x * x)
    return F(F(x * F(F(27.0) + x2)) * recip(F(F(27.0) + F(F(9.0) * x2))))


class Voice:
    """RUBBER on one slot"""

    def __init__(self):
        self.s = [F(0.0)] * 4
        self.gp = F(0.0)                  # the stages' coefficient at the last block's end (0: none yet)
        self.stage = 0                    # 0 off, 1 attack, 2 decay
        self.u = F(0.0)                   # the segment's position 0..1
        self.env = F(0.0)

    def block(self, rec: dict, trig: bool, nn, x: np.ndarray) -> np.ndarray:
        """REC: the record's floats by offset (FIELDS); NN the note; X the slot's 32 samples -> 32"""
        typ, freq, res = F(rec[R_TYPE]), F(rec[R_FREQ]), F(rec[R_RES])
        if trig:
            self.stage = 1
            self.u = F(0.0)
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
        # the cutoff (a note number): FREQ, key tracking, the envelope
        note = F(F(freq * F(128.0)) + F(F(rec[R_KEYT]) * F(nn - F(60.0))))
        note = F(note + F(F(F(F(rec[R_DEPTH]) - F(0.5)) * F(144.0)) * self.env))
        hz = note_hz(note)
        hz = F(min(max(hz, F_MIN), F_MAX))
        w = F(hz * F(PI_2FS * INV_PI))
        g = F(sin_turns(w) * recip(sin_turns(F(w + F(0.25)))))      # tan(pi f / fs)
        g1 = F(g * recip(F(F(1.0) + g)))                              # a stage's G
        g0 = self.gp if self.gp > F(0.0) else g1
        dg = F(F(g1 - g0) * INV_SUB)
        self.gp = g1
        kq = F(F(res * F(F(0.7) + F(F(0.3) * res))) * K_MAX)
        g2 = F(g1 * g1)
        den = recip(F(F(1.0) + F(kq * F(g2 * g2))))                   # the loop's solve (the block's end G)
        drive = F(F(1.0) + F(typ * DRIVE_SPAN))
        ing = F(drive * F(F(1.0) + F(kq * COMP)))
        outg = recip(F(F(0.6) + F(F(0.4) * drive)))
        s1, s2, s3, s4 = self.s
        gg = g0
        y = np.zeros(SUB, np.float32)
        for i in range(SUB):
            gg = F(gg + dg)
            om = F(F(1.0) - gg)
            q2 = F(gg * gg)
            q3 = F(q2 * gg)
            sm = F(F(F(F(F(q3 * s1) + F(q2 * s2)) + F(gg * s3)) + s4) * om)
            u = sat(F(F(F(F(x[i]) * ing) - F(kq * sm)) * den))
            y1 = F(s1 + F(gg * F(u - s1)))
            s1 = F(F(F(2.0) * y1) - s1)
            y2 = F(s2 + F(gg * F(y1 - s2)))
            s2 = F(F(F(2.0) * y2) - s2)
            y3 = F(s3 + F(gg * F(y2 - s3)))
            s3 = F(F(F(2.0) * y3) - s3)
            y4 = F(s4 + F(gg * F(y3 - s4)))
            s4 = F(F(F(2.0) * y4) - s4)
            y[i] = F(y4 * outg)
        self.s = [s1, s2, s3, s4]
        return y
