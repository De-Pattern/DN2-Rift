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

from ..organ.live import F, DT, recip, sin_turns, note_hz

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
QUART = F(0.25)
DC_R = F(0.995)
ID_DRIFT = F(F(0.13) * DT)              # the drift's own slow wander, 0.13 Hz, turns a sample
THIRD = F(F(1.0) / F(3.0))
# Every operation below is the DSP program's, in its order (dnfw.contour.program): float32 after each,
# phases wrapped by frac (fascia's leaf), no floor elsewhere.


def frac(x):
    x = F(x)
    return F(x - F(np.floor(x)))


def surface(s, x, y):
    """the eight surfaces, x and y about -1..1, z about -1..1"""
    if s == 0:                                  # SINE: a sine field
        return F(sin_turns(F(x * HALF)) * sin_turns(F(F(y * HALF) + QUART)))
    if s == 1:                                  # FOLD: the plane folded along its diagonal (a triangle)
        t = frac(F(F(F(x + y) * F(0.75)) + QUART))
        return F(F(F(4.0) * abs(F(t - HALF))) - F(1.0))
    if s == 2:                                  # CHEB: T3(x) T2(y)
        x2 = F(x * x)
        t3 = F(x * F(F(F(4.0) * x2) - F(3.0)))
        t2 = F(F(F(2.0) * F(y * y)) - F(1.0))
        return F(F(t3 * t2) * F(0.8))
    if s == 3:                                  # FM: X carried, Y modulating
        return sin_turns(F(F(x * HALF) + F(F(0.35) * sin_turns(F(y * F(1.5))))))
    if s == 4:                                  # RING: rings round a point off the centre
        xo = F(x + F(0.35))
        return sin_turns(F(F(F(xo * xo) + F(F(y * y) * F(0.6))) * F(1.5)))
    if s == 5:                                  # EDGE: a sine pushed hard against its ridge
        a = F(F(sin_turns(F(x * HALF)) * F(4.0)) * sin_turns(F(F(y * QUART) + QUART)))
        return F(a * recip(F(F(1.0) + abs(a))))
    if s == 6:                                  # CHAOS: a product folded on itself
        return sin_turns(F(F(F(x * y) * F(2.0)) + F(x * F(0.75))))
    tx = F(F(x * F(4.0)) + HALF)                # BITS: the plane in steps
    xq = F(F(tx - frac(tx)) * QUART)
    ty = F(F(y * F(3.0)) + HALF)
    yq = F(F(ty - frac(ty)) * THIRD)
    return F(sin_turns(F(xq * HALF)) * sin_turns(F(F(yq * HALF) + QUART)))


class Voice:
    def __init__(self, sr=FS):
        self.on = False
        self.px = self.py = self.pd = self.z = self.hold = self.gc = self.dcx = self.dcy = F(0.0)

    def note_on(self):
        self.on = True
        self.px = self.py = self.z = self.hold = self.gc = self.dcx = self.dcy = F(0.0)

    def block(self, k: dict, note: float, trig: bool = False, n: int = BLOCK) -> np.ndarray:
        if trig:
            self.note_on()
        out = np.zeros(n, np.float32)
        if not self.on:
            return out
        q = {c: F(F(k[c]) * INV127) for c in CONTROLS}
        hz = note_hz(F(F(note) + F(F(F(k["TUNE"]) - F(64.0)) * F(0.375))))   # +-24 semitones
        ix = F(hz * DT)
        iy = F(ix * RATIOS[min(int(k["RATIO"]) >> 3, 15)])
        sx, sy = q["SIZX"], q["SIZY"]
        cx = F(F(F(k["CNTX"]) - F(64.0)) * INV64)
        cy = F(F(F(k["CNTY"]) - F(64.0)) * INV64)
        ca = sin_turns(F(F(q["ROT"] * HALF) + QUART))
        sa = sin_turns(F(q["ROT"] * HALF))
        drft = F(F(q["DRFT"] * q["DRFT"]) * F(0.6))
        s0 = int(np.int32(np.trunc(F(F(k["SURF"]) * F(0.0625)))))
        s1 = (s0 + 1) & 7
        mo = q["MORPH"]
        warp = F(q["WARP"] * F(0.8))
        fold = F(q["FOLD"] * F(3.0))
        fold1 = F(F(1.0) + fold)
        fm = F(q["FM"] * F(1.5))
        # v0.20 (owner, 2026-11-23: "too extreme beyond about 38 ... amazing before that, especially
        # in the first 5 or so steps"): the whole knob is the old 0..~36, curved so the old first
        # 5 steps take about the first 36 (fb = u (0.0175 + 0.0525 u), 0.07 at 127; was 0.25 u)
        fb = F(q["FDBK"] * F(F(q["FDBK"] * F(0.0525)) + F(0.0175)))
        grit = F(int(k["GRIT"]) >> 3)
        lev = F(q["LEV"] * F(0.8))
        for i in range(n):
            self.px = frac(F(self.px + F(ix + F(fb * self.z))))
            self.py = frac(F(self.py + F(iy + F(fb * self.z))))
            self.pd = frac(F(self.pd + ID_DRIFT))
            dr = F(drft * sin_turns(self.pd))
            uy = sin_turns(F(F(self.py + QUART) + dr))
            ux = sin_turns(F(F(self.px + F(fm * uy)) + dr))
            x0 = F(sx * ux)
            y0 = F(sy * uy)
            x = F(F(F(x0 * ca) - F(y0 * sa)) + cx)
            y = F(F(F(x0 * sa) + F(y0 * ca)) + cy)
            x = F(x + F(warp * F(y * y)))
            z = surface(s0, x, y)
            if mo > F(0.0):
                zb = surface(s1, x, y)
                z = F(z + F(mo * F(zb - z)))
            if fold > F(0.0):
                z = sin_turns(F(F(z * fold1) * QUART))
            self.z = z
            if self.gc > F(0.0):
                self.gc = F(self.gc - F(1.0))
            else:
                self.hold = z
                self.gc = grit
            yy = F(F(self.hold - self.dcx) + F(DC_R * self.dcy))
            self.dcx = self.hold
            self.dcy = yy
            out[i] = F(yy * lev)
        return out
