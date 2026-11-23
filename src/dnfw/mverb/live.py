"""RIFT's master reverb (v0.21): Dattorro's plate (PLATEAU's tank, `dnfw.plateau.live`) in the stock
reverb's place on the FX block, on the SHARC's arithmetic (docs/master-reverb.md).

The owner (2026-11-23): "replace the stock master reverb with Plateau ... I wouldn't think it would be
smart to change the UI or controls on the master reverb". So the stock reverb's page and records are
kept, and only its core is replaced: the stock input stage (sends, the input HPF and LPF) still makes
the 32 mono samples the core reads, and the stock mix stage (MIX VOL, routing) still takes the 64 it
writes. The core's controls come from the frame's FX slot (its reverb words, docs/master-reverb.md):

- PRE: the pre-delay, 0..0.3 s.
- DEC: the tank's decay, from a short room to a long plate.
- FREQ, GAIN (the stock "feedback shelving"): a high shelf in the tank's loop. FREQ is the shelf's
  corner (500 Hz .. 19 kHz), GAIN how much of the band above it stays (0: all of it damped; 127: none).

Always on, stereo (Dattorro's Table 2: the first seven taps the left, the last seven the right), one
instance. Float32 after every operation, ORGAN's leaves (recip, exp2f, expf, sin_turns); no tanh, pow
or division. The DSP program (program.py) is held to this bit for bit.
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, recip, exp2f, expf, sin_turns
from ..plateau import live as PL

FS = 48000
SUB = 32
INV_T = F(F(1.0) / F(32512.0))        # a frame word: 0x7f00 is 1.0
IN_MAX = F(64.0)
WMASK = 0xFFFFFF
CHUNK = 4096                          # words cleared a block while a fresh instance starts (silent)
KR = PL.KR

# the lines: the plate's tank and input allpasses, and the pre-delay (0.3 s: 14,400 samples)
TANK = PL.TANK
IN_AP = PL.IN_AP
PRE = ("pre", 0, 16384)
LINES = TANK + IN_AP + (PRE,)
OFF = {}
_at = 0
for _n, _l, _s in LINES:
    OFF[_n] = _at
    _at += _s
TOTAL = _at
SIZE = {n: s for n, _l, s in LINES}
LEN = {n: int(np.trunc(F(F(l) * KR))) for n, l, _s in TANK + IN_AP}
TAPS = PL.TAPS
TAPK = tuple(int(np.trunc(F(F(t) * KR))) for _l, t, _s in TAPS)
EXC = F(F(16.0) * KR)                 # Table 1's excursion
LFO_INC = F(F(1.0) * F(F(SUB) / F(FS)))   # 1 Hz, a block's step (turns)
PRED_K = F(F(0.3) * F(48000.0))
OUT_K = F(0.6)                        # Dattorro's output gain, a side
INV_SUB = F(F(1.0) / F(32.0))
HMAX = F(F(0.45) * F(48000.0))
TWOPI_FS = PL.TWOPI_FS
GI1, GI2 = F(0.75), F(0.625)
GD1 = F(-0.7)


def onepole(hz):
    hz = F(hz)
    if hz > HMAX:
        hz = HMAX
    return F(F(1.0) - expf(F(F(0.0) - F(TWOPI_FS * hz))))


def trunc(x) -> int:
    return int(np.trunc(np.float32(x)))


def controls(pre: int, dec: int, freq: int, gain: int) -> dict:
    """the frame's four words (0..0x7f00) -> the block's settings, in the program's order"""
    p = F(F(pre) * INV_T)
    d = F(F(dec) * INV_T)
    fq = F(F(freq) * INV_T)
    g = F(F(gain) * INV_T)
    u = F(F(1.0) - d)
    gdec = F(min(F(F(0.1) + F(F(0.88) * F(F(1.0) - F(u * u)))), F(0.98)))
    return {"pred": trunc(F(p * PRED_K)), "gdec": gdec,
            "gd2": F(min(max(F(gdec + F(0.15)), F(0.25)), F(0.5))),
            "c_sh": onepole(F(F(500.0) * exp2f(F(fq * F(5.25))))), "g_sh": g}


class Verb:
    """the one instance"""

    def __init__(self):
        self.buf = np.zeros(TOTAL, np.float32)
        self.clr = 0                      # a fresh instance clears its lines first
        self.w = 0
        self.ph = F(0.0)
        self.shA = self.shB = F(0.0)
        self.endA = self.endB = F(0.0)

    def rd(self, line: str, d: int) -> np.float32:
        return self.buf[OFF[line] + ((self.w - d) & (SIZE[line] - 1))]

    def wr(self, line: str, v) -> None:
        self.buf[OFF[line] + (self.w & (SIZE[line] - 1))] = v

    def ap(self, line: str, x, d: int, g):
        z = self.rd(line, d)
        v = F(x - F(g * z))
        self.wr(line, v)
        return F(z + F(g * v))

    def apf(self, line: str, x, d, g):
        di = trunc(d)
        fr = F(d - F(di))
        b0 = self.rd(line, di)
        b1 = self.rd(line, di + 1)
        z = F(b0 + F(F(b1 - b0) * fr))
        v = F(x - F(g * z))
        self.wr(line, v)
        return F(z + F(g * v))

    def block(self, words: tuple[int, int, int, int], x_in: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """WORDS: the frame's PRE, DEC, FREQ, GAIN; X_IN the 32 input samples -> (left, right)"""
        if self.clr < TOTAL:
            self.buf[self.clr:self.clr + CHUNK] = 0.0
            self.clr += CHUNK
            return np.zeros(SUB, np.float32), np.zeros(SUB, np.float32)
        c = controls(*words)
        gdec, gd2, c_sh, g_sh, pred = c["gdec"], c["gd2"], c["c_sh"], c["g_sh"], c["pred"]
        ph0 = self.ph
        ph1 = F(ph0 + LFO_INC)
        if ph1 >= F(1.0):
            ph1 = F(ph1 - F(1.0))
        ma = F(EXC * F(F(1.0) + sin_turns(ph0)))
        mb = F(EXC * F(F(1.0) + sin_turns(F(ph0 + F(0.25)))))
        dma = F(F(F(EXC * F(F(1.0) + sin_turns(ph1))) - ma) * INV_SUB)
        dmb = F(F(F(EXC * F(F(1.0) + sin_turns(F(ph1 + F(0.25))))) - mb) * INV_SUB)
        fa = F(LEN["a_ap"])
        fb = F(LEN["b_ap"])
        L = np.zeros(SUB, np.float32)
        R = np.zeros(SUB, np.float32)
        for i in range(SUB):
            x = F(x_in[i])
            if not (abs(x) < IN_MAX):
                x = F(0.0)
            self.wr("pre", x)
            if pred > 0:
                x = self.rd("pre", pred)
            x = self.ap("i0", x, LEN["i0"], GI1)
            x = self.ap("i1", x, LEN["i1"], GI1)
            x = self.ap("i2", x, LEN["i2"], GI2)
            x = self.ap("i3", x, LEN["i3"], GI2)
            a = self.apf("a_ap", F(x + F(gdec * self.endB)), F(fa + ma), GD1)
            self.wr("a_d1", a)
            a = self.rd("a_d1", LEN["a_d1"])
            self.shA = F(self.shA + F(c_sh * F(a - self.shA)))          # the shelf: lows kept, highs x GAIN
            a = F(F(self.shA + F(g_sh * F(a - self.shA))) * gdec)
            a = self.ap("a_ap2", a, LEN["a_ap2"], gd2)
            self.wr("a_d2", a)
            na = self.rd("a_d2", LEN["a_d2"])
            b = self.apf("b_ap", F(x + F(gdec * self.endA)), F(fb + mb), GD1)
            self.wr("b_d1", b)
            b = self.rd("b_d1", LEN["b_d1"])
            self.shB = F(self.shB + F(c_sh * F(b - self.shB)))
            b = F(F(self.shB + F(g_sh * F(b - self.shB))) * gdec)
            b = self.ap("b_ap2", b, LEN["b_ap2"], gd2)
            self.wr("b_d2", b)
            nb = self.rd("b_d2", LEN["b_d2"])
            self.endA, self.endB = na, nb
            yl = F(0.0)
            yr = F(0.0)
            for k, ((line, _t, sg), d) in enumerate(zip(TAPS, TAPK)):
                v = self.rd(line, d)
                if k < 7:
                    yl = F(yl + v) if sg > 0 else F(yl - v)
                else:
                    yr = F(yr + v) if sg > 0 else F(yr - v)
            L[i] = F(yl * OUT_K)
            R[i] = F(yr * OUT_K)
            ma = F(ma + dma)
            mb = F(mb + dmb)
            self.w = (self.w + 1) & WMASK
        self.ph = ph1
        return L, R
