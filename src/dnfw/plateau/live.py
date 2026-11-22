"""PLATEAU's voice on the SHARC's arithmetic (RIFT v0.17, the first FX machine: docs/fx-machines.md).

Dattorro's plate (J. AES 45/9, 1997, Fig. 1 and Tables 1-2), the reference model being
`dnfw.fx.plateau` (the owner's auditions, 2026-11-21), rebuilt for the DSP. Float32 after every
operation, Ravel's leaves from organ.live (recip, exp2f, expf, sin_turns, note_hz), no tanh, pow or
division. The SHARC program (program.py) is held to this bit for bit.

Differences from the reference model, for the DSP's cost:
- **Mono, all wet** (owner: the FX track is mono, its sources keep their own dry output): the
  input is the bus (the chosen tracks' blocks, L + R), the output Table 2's fourteen taps summed
  (both sides), into the track's own voice buffer.
- **The lines are powers of two, one write counter for them all** (`w`): a read is
  `buf[(w - d) & mask]`, no pointer a line. Every length and tap is an integer, set once a block;
  only the two modulated allpasses read between samples (linear).
- **The modulation** is set once a block: the LFO's two ends (sin and its quarter-turn), the
  excursion ramped across the block's 32 samples.
- **DRV** (new): a soft clip (DIGIDRUM's `sat`) in each half of the tank, so HOLD's endless loop and
  a loud bus stay bounded. **ERLY** (new): the diffused input into the output.
- **One instance.** The lines (336 KB of DDR) are one; the newest voice to start on them owns them
  (`owner`), an older one goes quiet. A fresh instance clears them first, a part a block.

Controls (knobs 0..127): FX1 PLATE: PRED SIZE DCAY DIFF / DAMP BAND LCUT LEV;
FX2 TANK: TLOW MSPD MDEP HOLD / TUND IGN DRV ERLY. HOLD and TUND are OFF/ON.
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, recip, exp2f, expf, sin_turns, note_hz

FS = 48000
SUB = 32
INV127 = F(F(1.0) / F(127.0))
KR = F(F(48000.0) / F(29761.0))      # Dattorro's lengths are at 29,761 Hz
IDLE = F(1.0e-5)
IN_MAX = F(64.0)                     # an input sample not under this (or not a number) is taken as 0
QUIET_BLOCKS = 1500                  # a second of silence in and out: the voice rests
CHUNK = 4096                         # words cleared a block while a fresh instance starts
WMASK = 0xFFFFFF

PAGE1 = ("PRED", "SIZE", "DCAY", "DIFF", "DAMP", "BAND", "LCUT", "LEV")
PAGE2 = ("TLOW", "MSPD", "MDEP", "HOLD", "TUND", "IGN", "DRV", "ERLY")
CONTROLS = PAGE1 + PAGE2
SWITCHES = ("HOLD", "TUND")

# the lines: (name, Dattorro's length, size: a power of two above its longest use)
TANK = (("a_ap", 672, 2048), ("a_d1", 4453, 8192), ("a_ap2", 1800, 4096), ("a_d2", 3720, 8192),
        ("b_ap", 908, 2048), ("b_d1", 4217, 8192), ("b_ap2", 2656, 8192), ("b_d2", 3163, 8192))
IN_AP = (("i0", 142, 256), ("i1", 107, 256), ("i2", 379, 1024), ("i3", 277, 512))
PRE = ("pre", 0, 32768)              # PRED: up to half a second
LINES = TANK + IN_AP + (PRE,)
OFF = {}
_at = 0
for _n, _l, _s in LINES:
    OFF[_n] = _at
    _at += _s
TOTAL = _at                           # 83,968 words
SIZE = {n: s for n, _l, s in LINES}
LK = {n: F(F(l) * KR) for n, l, _s in TANK + IN_AP}
# Table 2's taps, left then right, as one mono sum: (line, tap, sign)
TAPS = (("b_d1", 266, 1), ("b_d1", 2974, 1), ("b_ap2", 1913, -1), ("b_d2", 1996, 1),
        ("a_d1", 1990, -1), ("a_ap2", 187, -1), ("a_d2", 1066, -1),
        ("a_d1", 353, 1), ("a_d1", 3627, 1), ("a_ap2", 1228, -1), ("a_d2", 2673, 1),
        ("b_d1", 2111, -1), ("b_ap2", 335, -1), ("b_d2", 121, -1))
TK = tuple(F(F(t) * KR) for _l, t, _s in TAPS)
LOOP = sum(l for _n, l, _s in TANK)
C8 = F(F(F(FS) * F(8.0)) * recip(F(F(LOOP) * KR)))   # TUND: eight periods round the figure eight
EXCK = F(F(F(16.0) * KR) * F(2.0))                   # Table 1's excursion (16), at MDEP 127 and SIZE 1
TWOPI_FS = F(F(6.28318530717958647692) * F(F(1.0) / F(48000.0)))
HMAX = F(F(0.45) * F(48000.0))
PRED_K = F(F(0.5) * F(48000.0))
OUT_K = F(0.3)                       # 0.6 a side, the two sides summed and halved
INV_SUB = F(F(1.0) / F(32.0))
INV100 = F(F(1.0) / F(100.0))


def sat(x):
    """DIGIDRUM's tanh stand-in: x (27 + x^2) / (27 + 9 x^2), +-1 beyond |x| = 3"""
    x = F(x)
    if x >= F(3.0):
        return F(1.0)
    if x <= F(-3.0):
        return F(-1.0)
    x2 = F(x * x)
    return F(F(x * F(F(27.0) + x2)) * recip(F(F(27.0) + F(F(9.0) * x2))))


def onepole(hz):
    """1 - e^(-2 pi f / fs), f at most 0.45 fs"""
    hz = F(hz)
    if hz > HMAX:
        hz = HMAX
    return F(F(1.0) - expf(F(F(0.0) - F(TWOPI_FS * hz))))


def trunc(x) -> int:
    return int(np.trunc(np.float32(x)))


class Shared:
    """the one instance's DDR: the lines and the owner word"""

    def __init__(self):
        self.buf = np.zeros(TOTAL, np.float32)
        self.owner = 0


class Voice:
    """one slot's PLATEAU (slot T)"""

    def __init__(self, t: int, shared: Shared | None = None):
        self.t = t
        self.sh = shared or Shared()
        self.fresh = True
        self.on = 0
        self.w = 0
        self.clr = TOTAL
        self.quiet = 0
        self.ph = F(0.0)
        self.lp_in = self.hp_in = F(0.0)
        self.dampA = self.dampB = self.hpA = self.hpB = F(0.0)
        self.endA = self.endB = F(0.0)

    # -- the lines ------------------------------------------------------------------------------------
    def rd(self, line: str, d: int) -> np.float32:
        return self.sh.buf[OFF[line] + ((self.w - d) & (SIZE[line] - 1))]

    def wr(self, line: str, v) -> None:
        self.sh.buf[OFF[line] + (self.w & (SIZE[line] - 1))] = v

    def ap(self, line: str, x, d: int, g):
        z = self.rd(line, d)
        v = F(x - F(g * z))
        self.wr(line, v)
        return F(z + F(g * v))

    def apf(self, line: str, x, d, g):
        """the modulated allpass: its delay D between samples (linear)"""
        di = trunc(d)
        fr = F(d - F(di))
        b0 = self.rd(line, di)
        b1 = self.rd(line, di + 1)
        z = F(b0 + F(F(b1 - b0) * fr))
        v = F(x - F(g * z))
        self.wr(line, v)
        return F(z + F(g * v))

    # -- a block --------------------------------------------------------------------------------------
    def block(self, k: dict, trig: bool, nn, bus: np.ndarray) -> np.ndarray:
        """K: the controls (0..127; HOLD and TUND 0/1); NN the note; BUS: the input, L + R summed
        over the chosen tracks (32 floats, the program's own sum). -> 32 floats"""
        out = np.zeros(SUB, np.float32)
        me = self.t + 1
        if self.fresh:
            self.fresh = False
            self.on = 0
            self.w = 0
            self.clr = 0
            self.quiet = 0
            self.ph = F(0.0)
            self.lp_in = self.hp_in = F(0.0)
            self.dampA = self.dampB = self.hpA = self.hpB = F(0.0)
            self.endA = self.endB = F(0.0)
            self.sh.owner = me
        if trig:
            self.on = 1
            self.quiet = 0
            self.sh.owner = me
        if not self.on:
            return out
        if self.sh.owner != me:
            self.on = 0
            return out
        if self.clr < TOTAL:
            self.sh.buf[self.clr:self.clr + CHUNK] = 0.0
            self.clr += CHUNK
            return out
        q = {c: F(F(k[c]) * INV127) for c in CONTROLS if c not in SWITCHES}
        if k["TUND"]:
            s = F(C8 * recip(note_hz(nn)))
            scale = F(min(max(s, F(0.002)), F(1.0)))
        else:
            scale = F(F(0.02) + F(F(0.98) * F(q["SIZE"] * q["SIZE"])))
        ln = {n: trunc(max(F(LK[n] * scale), F(2.0))) for n, _l, _s in TANK}
        sci = F(min(F(scale * F(1.6)), F(1.0)))
        il = [trunc(max(F(LK[n] * sci), F(1.0))) for n, _l, _s in IN_AP]
        taps = [trunc(max(F(tk * scale), F(1.0))) for tk in TK]
        pred = trunc(F(q["PRED"] * PRED_K))
        c_band = onepole(F(F(200.0) * exp2f(F(q["BAND"] * F(6.6)))))
        c_lc = onepole(F(F(10.0) * exp2f(F(q["LCUT"] * F(9.0)))))
        c_tl = onepole(F(F(10.0) * exp2f(F(q["TLOW"] * F(9.0)))))
        c_dp = onepole(F(F(19000.0) * exp2f(F(F(0.0) - F(q["DAMP"] * F(6.6))))))
        if k["HOLD"]:
            gdec = F(1.0)
        else:
            u = F(F(1.0) - q["DCAY"])
            gdec = F(min(F(F(0.1) + F(F(0.9) * F(F(1.0) - F(u * u)))), F(0.9999)))
        d2 = F(min(max(F(gdec + F(0.15)), F(0.25)), F(0.5)))
        diff = q["DIFF"]
        gi1, gi2 = F(F(0.75) * diff), F(F(0.625) * diff)
        gd1 = F(F(0.0) - F(F(0.7) * diff))
        gd2 = F(d2 * diff)
        inc = F(F(F(0.05) * exp2f(F(q["MSPD"] * F(8.0)))) * F(F(SUB) / F(FS)))
        exc = F(F(EXCK * scale) * q["MDEP"])
        ph0 = self.ph
        ph1 = F(ph0 + inc)
        if ph1 >= F(1.0):
            ph1 = F(ph1 - F(1.0))
        ma = F(exc * F(F(1.0) + sin_turns(ph0)))
        mb = F(exc * F(F(1.0) + sin_turns(F(ph0 + F(0.25)))))
        dma = F(F(F(exc * F(F(1.0) + sin_turns(ph1))) - ma) * INV_SUB)
        dmb = F(F(F(exc * F(F(1.0) + sin_turns(F(ph1 + F(0.25))))) - mb) * INV_SUB)
        ig = q["IGN"]
        hig = F(F(2.0) * F(ig * ig))
        drv = q["DRV"]
        dg = F(F(1.0) + F(F(8.0) * F(drv * drv)))
        rdg = recip(dg)
        erly = q["ERLY"]
        lev = F(F(k["LEV"]) * INV100)
        fa = F(F(ln["a_ap"]))
        fb = F(F(ln["b_ap"]))
        peak = F(0.0)
        ipk = F(0.0)
        for i in range(SUB):
            x = F(0.0) if k["HOLD"] else F(bus[i] * hig)
            if not (abs(x) < IN_MAX):            # (a NaN or a runaway on the bus never reaches the lines)
                x = F(0.0)
            ipk = max(ipk, F(abs(x)))
            self.wr("pre", x)
            if pred > 0:
                x = self.rd("pre", pred)
            self.lp_in = F(self.lp_in + F(c_band * F(x - self.lp_in)))
            self.hp_in = F(self.hp_in + F(c_lc * F(self.lp_in - self.hp_in)))
            x = F(self.lp_in - self.hp_in)
            x = self.ap("i0", x, il[0], gi1)
            x = self.ap("i1", x, il[1], gi1)
            x = self.ap("i2", x, il[2], gi2)
            x = self.ap("i3", x, il[3], gi2)
            # half A
            a = self.apf("a_ap", F(x + F(gdec * self.endB)), F(fa + ma), gd1)
            self.wr("a_d1", a)
            a = self.rd("a_d1", ln["a_d1"])
            self.dampA = F(self.dampA + F(c_dp * F(a - self.dampA)))
            self.hpA = F(self.hpA + F(c_tl * F(self.dampA - self.hpA)))
            a = F(F(self.dampA - self.hpA) * gdec)
            if drv > F(0.0):
                a = F(sat(F(a * dg)) * rdg)
            a = self.ap("a_ap2", a, ln["a_ap2"], gd2)
            self.wr("a_d2", a)
            na = self.rd("a_d2", ln["a_d2"])
            # half B
            b = self.apf("b_ap", F(x + F(gdec * self.endA)), F(fb + mb), gd1)
            self.wr("b_d1", b)
            b = self.rd("b_d1", ln["b_d1"])
            self.dampB = F(self.dampB + F(c_dp * F(b - self.dampB)))
            self.hpB = F(self.hpB + F(c_tl * F(self.dampB - self.hpB)))
            b = F(F(self.dampB - self.hpB) * gdec)
            if drv > F(0.0):
                b = F(sat(F(b * dg)) * rdg)
            b = self.ap("b_ap2", b, ln["b_ap2"], gd2)
            self.wr("b_d2", b)
            nb = self.rd("b_d2", ln["b_d2"])
            self.endA, self.endB = na, nb
            y = F(0.0)
            for (line, _t, sg), d in zip(TAPS, taps):
                v = self.rd(line, d)
                y = F(y + v) if sg > 0 else F(y - v)
            y = F(y * OUT_K)
            if erly > F(0.0):
                y = F(y + F(erly * x))
            y = F(y * lev)
            out[i] = y
            peak = max(peak, F(abs(y)))
            ma = F(ma + dma)
            mb = F(mb + dmb)
            self.w = (self.w + 1) & WMASK
        self.ph = ph1
        if peak < IDLE and ipk < IDLE:
            self.quiet += 1
            if self.quiet > QUIET_BLOCKS:
                self.on = 0
        else:
            self.quiet = 0
        return out


def bus_sum(blocks_l, blocks_r, mask: int, mine: int) -> np.ndarray:
    """the program's input: for each track in MASK but MINE, in order, inb += (L + R)"""
    inb = np.zeros(SUB, np.float32)
    for t in range(16):
        if mask >> t & 1 and t != mine:
            for i in range(SUB):
                inb[i] = F(inb[i] + F(blocks_l[t][i] + blocks_r[t][i]))
    return inb
