"""CONTOUR (RIFT v0.20, owner 2026-11-22): wave-terrain synthesis, on the SHARC's arithmetic.

A point (x, y) orbits over a surface z = f(x, y); its height z is the sample. The orbit is an
ellipse traced at the note's pitch on X and RATIO times it on Y, sized by SIZX/SIZY, centred at
CNTX/CNTY, turned by ROT and wandering with DRFT. The surface is one of eight (SURF), blended into
the next by MORPH; WARP bends the plane under the orbit, FM moves X by the Y orbit, FDBK feeds the
last height back into both phases, FOLD folds the height, GRIT holds samples (a decimator), LEV
sets the level. RIFT's own: the idea of TERRAIN (ycmdynp9vw-coder/terrain-dn2), none of its code.

float32 after every operation, Ravel's leaves (organ.live: sin_turns, exp2f, note_hz, recip, xs_bi)
so the SHARC program can be held to it bit for bit.

Controls (0..127). Page 1 ORBIT: TUNE RATIO SIZX SIZY / CNTX CNTY ROT DRFT.
Page 2 LAND: SURF MORPH WARP FOLD / FM FDBK GRIT LEV.
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, DT, recip, exp2f, sin_turns, note_hz, floorf

FS = 48000
BLOCK = 32
PAGE1 = ("TUNE", "RATIO", "SIZX", "SIZY", "CNTX", "CNTY", "ROT", "DRFT")
PAGE2 = ("SURF", "MORPH", "WARP", "FOLD", "FM", "FDBK", "GRIT", "LEV")
CONTROLS = PAGE1 + PAGE2
DEFAULTS = dict(TUNE=64, RATIO=40, SIZX=90, SIZY=90, CNTX=64, CNTY=64, ROT=0, DRFT=0,
                SURF=0, MORPH=0, WARP=0, FOLD=0, FM=0, FDBK=0, GRIT=0, LEV=100)
SURFACES = ("SINE", "FOLD", "CHEB", "FM", "RING", "EDGE", "CHAOS", "BITS")
# Y's speed against X's: the musical ratios, then the beating ones
RATIOS = tuple(F(v) for v in (0.25, 1 / 3, 0.5, 2 / 3, 0.75, 1.0, 1.0025, 1.25, 4 / 3, 1.5, 2.0, 2.5, 3.0,
                              4.0, 5.0, 7.0))
INV127 = F(F(1.0) / F(127.0))
INV64 = F(F(1.0) / F(64.0))
HALF = F(0.5)
DC_R = F(0.995)
IDLE = F(1.0e-5)


def knob(k):
    return F(F(k) * INV127)


def bip(k):
    """-1 .. +1, 64 is 0"""
    return F(F(F(k) - F(64.0)) * INV64)


def tri(u):
    """a triangle of u in turns: +-1, as a fold"""
    t = F(u - floorf(u))
    return F(F(F(4.0) * abs(F(t - HALF))) - F(1.0))


def surface(s, x, y):
    """the eight surfaces, x and y about -1..1, z about -1..1"""
    if s == 0:                                  # SINE: a sine field
        return F(sin_turns(F(x * HALF)) * sin_turns(F(F(y * HALF) + F(0.25))))
    if s == 1:                                  # FOLD: the plane folded along its diagonal
        return tri(F(F(F(x + y) * F(0.75)) + F(0.25)))
    if s == 2:                                  # CHEB: T3(x) T2(y)
        x2 = F(x * x)
        t3 = F(x * F(F(F(4.0) * x2) - F(3.0)))
        t2 = F(F(F(2.0) * F(y * y)) - F(1.0))
        return F(F(t3 * t2) * F(0.8))
    if s == 3:                                  # FM: X carried, Y modulating
        return sin_turns(F(F(x * HALF) + F(F(0.35) * sin_turns(F(y * F(1.5))))))
    if s == 4:                                  # RING: rings round a point off the centre (a centred circle reads one height)
        xo = F(x + F(0.35))
        return sin_turns(F(F(F(xo * xo) + F(F(y * y) * F(0.6))) * F(1.5)))
    if s == 5:                                  # EDGE: a sine squared hard against the ridge
        a = F(F(sin_turns(F(x * HALF)) * F(4.0)) * sin_turns(F(F(y * F(0.25)) + F(0.25))))
        return F(a * recip(F(F(1.0) + abs(a))))
    if s == 6:                                  # CHAOS: a product folded on itself
        return sin_turns(F(F(F(x * y) * F(2.0)) + F(x * F(0.75))))
    xq = F(floorf(F(F(x * F(4.0)) + HALF)) * F(0.25))   # BITS: the plane in steps
    yq = F(floorf(F(F(y * F(3.0)) + HALF)) * F(F(1.0) / F(3.0)))
    return F(sin_turns(F(xq * HALF)) * sin_turns(F(F(yq * HALF) + F(0.25))))


class Voice:
    def __init__(self, sr=FS):
        self.px = self.py = self.pd = F(0.0)
        self.z = F(0.0)
        self.hold = F(0.0)
        self.gc = F(0.0)
        self.dcx = self.dcy = F(0.0)
        self.on = False

    def note_on(self):
        self.px = self.py = F(0.0)
        self.z = self.hold = self.gc = F(0.0)
        self.dcx = self.dcy = F(0.0)
        self.on = True

    def block(self, k: dict, note: float, trig: bool = False, n: int = BLOCK) -> np.ndarray:
        if trig:
            self.note_on()
        out = np.zeros(n, np.float32)
        if not self.on:
            return out
        hz = note_hz(F(F(note) + F(F(F(k["TUNE"]) - F(64.0)) * F(0.375))))   # +-24 semitones
        ix = F(hz * DT)
        ri = min(int(k["RATIO"]) >> 3, 15)
        iy = F(ix * RATIOS[ri])
        sx, sy = knob(k["SIZX"]), knob(k["SIZY"])
        cxx, cyy = bip(k["CNTX"]), bip(k["CNTY"])
        rot = knob(k["ROT"])                    # turns of a half turn
        ca = sin_turns(F(F(rot * HALF) + F(0.25)))
        sa = sin_turns(F(rot * HALF))
        drft = F(F(knob(k["DRFT"]) * knob(k["DRFT"])) * F(0.6))
        id_ = F(F(0.13) * DT)                   # the drift's own slow wander (0.13 Hz)
        m = F(F(k["SURF"]) * F(8.0 / 128.0))
        s0 = int(m) & 7
        mo = knob(k["MORPH"])
        s1 = (s0 + 1) & 7
        warp = F(knob(k["WARP"]) * F(0.8))
        fold = F(knob(k["FOLD"]) * F(3.0))
        fm = F(knob(k["FM"]) * F(1.5))
        fb = F(knob(k["FDBK"]) * F(0.25))
        grit = int(k["GRIT"]) >> 3              # hold every 1 + grit samples
        lev = F(knob(k["LEV"]) * F(0.8))
        for i in range(n):
            self.px = F(self.px + F(ix + F(fb * self.z)))
            self.px = F(self.px - floorf(self.px))
            self.py = F(self.py + F(iy + F(fb * self.z)))
            self.py = F(self.py - floorf(self.py))
            self.pd = F(self.pd + id_)
            self.pd = F(self.pd - floorf(self.pd))
            dr = F(drft * sin_turns(self.pd))
            uy = sin_turns(F(F(self.py + F(0.25)) + dr))
            ux = sin_turns(F(F(self.px + F(fm * uy)) + dr))
            x0 = F(sx * ux)
            y0 = F(sy * uy)
            x = F(F(F(x0 * ca) - F(y0 * sa)) + cxx)
            y = F(F(F(x0 * sa) + F(y0 * ca)) + cyy)
            x = F(x + F(warp * F(y * y)))
            za = surface(s0, x, y)
            zb = surface(s1, x, y)
            z = F(za + F(mo * F(zb - za)))
            if fold > F(0.0):
                z = sin_turns(F(F(z * F(F(1.0) + fold)) * F(0.25)))
            self.z = z
            if self.gc <= F(0.0):
                self.hold = z
                self.gc = F(grit)
            else:
                self.gc = F(self.gc - F(1.0))
            # DC blocker
            y_ = F(F(self.hold - self.dcx) + F(DC_R * self.dcy))
            self.dcx = self.hold
            self.dcy = y_
            out[i] = F(y_ * lev)
        return out
