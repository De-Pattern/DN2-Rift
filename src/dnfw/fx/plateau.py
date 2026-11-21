"""PLATEAU: RIFT's plate reverb FX machine, reference model (owner, 2026-11-21: "an effect for the
fx machine which is based on the PLATEAU reverb for vcv rack").

Built from Jon Dattorro's "Effect Design, Part 1" (J. AES 45/9, 1997), Fig. 1 and Tables 1-2:
the plate-class network Valley's Plateau and 4ms' Mesa are also built on. Plateau's own code is
not used (ValleyRackFree's licence); its panel is the model for the controls on top of the
paper's network: SIZE, DIFFUSION, input and tank low/high cuts, modulation, HOLD, CLEAR, TUNED.

The network (Dattorro's node numbers in brackets), stereo in, stereo out, all wet:

    in = (L + R) / 2 -> PREDELAY -> input low pass (bandwidth) -> input high pass (LOW CUT)
       -> four input allpasses 142, 107, 379, 277 (input diffusion 0.75, 0.75, 0.625, 0.625)
       -> the tank, a figure eight of two halves:
          half A: in + decay * B's end -> modulated allpass 672+exc (-decay diffusion 1)
                  -> delay 4453 [24_30] -> damping low pass -> tank high pass -> * decay
                  -> allpass 1800 [31_33] (decay diffusion 2) -> delay 3720 [33_39] -> to B
          half B: in + decay * A's end -> modulated allpass 908+exc -> delay 4217 [48_54]
                  -> damping -> tank high pass -> * decay -> allpass 2656 [55_59]
                  -> delay 3163 [59_63] -> to A
    out: Table 2's fourteen taps (0.6 each), every delay and tap scaled by SIZE.

The lengths are Dattorro's at 29,761 Hz, scaled to 48 kHz and by SIZE. All state is float32 in
the model the DSP port will be bit-exact to (that port reads its own float32 `live` model, made
once the owner approves the sound, as every RIFT engine).
"""
from __future__ import annotations

import math

import numpy as np

RATE = 48000.0
DATTORRO_FS = 29761.0
EXCURSION = 16.0                      # Table 1: peak excursion of the tank's modulated taps
IN_AP = (142, 107, 379, 277)
TANK = {"a_ap": 672, "a_d1": 4453, "a_ap2": 1800, "a_d2": 3720,
        "b_ap": 908, "b_d1": 4217, "b_ap2": 2656, "b_d2": 3163}
# Table 2: (line, tap, sign) for the left and the right output
TAPS_L = (("b_d1", 266, 1), ("b_d1", 2974, 1), ("b_ap2", 1913, -1), ("b_d2", 1996, 1),
          ("a_d1", 1990, -1), ("a_ap2", 187, -1), ("a_d2", 1066, -1))
TAPS_R = (("a_d1", 353, 1), ("a_d1", 3627, 1), ("a_ap2", 1228, -1), ("a_d2", 2673, 1),
          ("b_d1", 2111, -1), ("b_ap2", 335, -1), ("b_d2", 121, -1))
SIZE_MAX = 1.0                        # the tank at Dattorro's own size (48 kHz: about 36,000 samples)
PRED_MAX = 0.5                        # 500 ms, as Plateau


def _onepole(hz: float) -> float:
    return 1.0 - math.exp(-2.0 * math.pi * min(hz, 0.45 * RATE) / RATE)


class Line:
    """A delay line with a write head; reads `d` samples back (fractional: linear)."""
    __slots__ = ("buf", "n", "w")

    def __init__(self, n: int):
        self.buf = [0.0] * n
        self.n = n
        self.w = 0

    def put(self, x: float) -> None:
        self.buf[self.w] = x
        self.w = self.w + 1 if self.w + 1 < self.n else 0

    def at(self, d: float) -> float:
        i = int(d)
        f = d - i
        r = self.w - 1 - i
        a = self.buf[r % self.n]
        b = self.buf[(r - 1) % self.n]
        return a + (b - a) * f

    def clear(self) -> None:
        self.buf = [0.0] * self.n


class Plateau:
    """One instance: stereo in, stereo out. Controls 0..1 (knob / 127) unless said."""

    def __init__(self, pred=0.0, size=0.6, decay=0.6, diff=1.0, damp=0.3, band=0.85, locut=0.05,
                 tlocut=0.05, mspd=0.25, mdep=0.3, hold=False, tuned=False, note=60.0,
                 dry=1.0, wet=0.5):
        k = RATE / DATTORRO_FS
        self.k = k
        self.maxlen = {n: int(L * k * SIZE_MAX) + 2 * int(EXCURSION * k) + 4 for n, L in TANK.items()}
        self.lines = {n: Line(m) for n, m in self.maxlen.items()}
        self.inap = [Line(int(L * k * SIZE_MAX) + 4) for L in IN_AP]
        self.pre = Line(int(PRED_MAX * RATE) + 4)
        self.lp_in = self.hp_in = self.hp_in_x = 0.0
        self.dampA = self.dampB = 0.0
        self.hpA = self.hpA_x = self.hpB = self.hpB_x = 0.0
        self.endA = self.endB = 0.0
        self.ph = 0.0
        self.set(pred=pred, size=size, decay=decay, diff=diff, damp=damp, band=band, locut=locut,
                 tlocut=tlocut, mspd=mspd, mdep=mdep, hold=hold, tuned=tuned, note=note, dry=dry, wet=wet)

    def set(self, **kw) -> None:
        for n, v in kw.items():
            setattr(self, n, v)
        k = self.k
        if self.tuned:                       # TUNED: the tank's loop is the note's period
            hz = 440.0 * 2.0 ** ((self.note - 69.0) / 12.0)
            loop = sum(TANK.values()) * k
            s = (RATE / hz) * 8.0 / loop     # (eight periods round the figure eight)
            self.scale = min(max(s, 0.002), SIZE_MAX)
        else:
            self.scale = 0.02 + (SIZE_MAX - 0.02) * self.size * self.size
        self.len = {n: max(2.0, L * k * self.scale) for n, L in TANK.items()}
        self.inlen = [max(1.0, L * k * min(self.scale * 1.6, SIZE_MAX)) for L in IN_AP]
        self.predly = self.pred * PRED_MAX * RATE
        self.c_band = _onepole(200.0 * 2.0 ** (self.band * 6.6))      # 200 Hz .. 19 kHz
        self.c_locut = _onepole(10.0 * 2.0 ** (self.locut * 9.0))     # 10 Hz .. 5 kHz
        self.c_tlocut = _onepole(10.0 * 2.0 ** (self.tlocut * 9.0))
        self.c_damp = _onepole(19000.0 * 2.0 ** (-self.damp * 6.6))   # tank high cut
        self.g_dec = 1.0 if self.hold else min(0.9999, 0.1 + 0.9 * (1.0 - (1.0 - self.decay) ** 2))
        d2 = min(0.5, max(0.25, self.g_dec + 0.15))
        self.g_in1, self.g_in2 = 0.75 * self.diff, 0.625 * self.diff
        self.g_dd1, self.g_dd2 = 0.70 * self.diff, d2 * self.diff
        self.lfo_inc = 0.05 * 2.0 ** (self.mspd * 8.0) / RATE           # 0.05 .. 12.8 Hz
        self.exc = EXCURSION * k * self.scale * self.mdep * 2.0

    def clear(self) -> None:
        for L in list(self.lines.values()) + self.inap + [self.pre]:
            L.clear()
        self.endA = self.endB = self.dampA = self.dampB = 0.0

    @staticmethod
    def _ap(line: Line, x: float, d: float, g: float) -> float:
        """Dattorro's lattice allpass: v = x - g*z; out = z + g*v; store v."""
        z = line.at(d - 1.0)
        v = x - g * z
        line.put(v)
        return z + g * v

    def run(self, L: np.ndarray, R: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        n = len(L)
        oL = np.zeros(n)
        oR = np.zeros(n)
        Ln = self.lines
        ln = self.len
        taps_l = [(Ln[a], t * self.k * self.scale, s) for a, t, s in TAPS_L]
        taps_r = [(Ln[a], t * self.k * self.scale, s) for a, t, s in TAPS_R]
        for i in range(n):
            x = 0.0 if self.hold else 0.5 * (float(L[i]) + float(R[i]))
            self.pre.put(x)
            x = self.pre.at(self.predly) if self.predly >= 1.0 else x
            self.lp_in += self.c_band * (x - self.lp_in)
            self.hp_in += self.c_locut * (self.lp_in - self.hp_in)
            x = self.lp_in - self.hp_in
            for j, ap in enumerate(self.inap):
                x = self._ap(ap, x, self.inlen[j], self.g_in1 if j < 2 else self.g_in2)
            self.ph += self.lfo_inc
            if self.ph >= 1.0:
                self.ph -= 1.0
            ma = self.exc * (1.0 + math.sin(2.0 * math.pi * self.ph))
            mb = self.exc * (1.0 + math.cos(2.0 * math.pi * self.ph))
            # half A
            a = self._ap(Ln["a_ap"], x + self.g_dec * self.endB, ln["a_ap"] + ma, -self.g_dd1)
            Ln["a_d1"].put(a)
            a = Ln["a_d1"].at(ln["a_d1"] - 1.0)
            self.dampA += self.c_damp * (a - self.dampA)
            self.hpA += self.c_tlocut * (self.dampA - self.hpA)
            a = (self.dampA - self.hpA) * self.g_dec
            a = self._ap(Ln["a_ap2"], a, ln["a_ap2"], self.g_dd2)
            Ln["a_d2"].put(a)
            endA = Ln["a_d2"].at(ln["a_d2"] - 1.0)
            # half B
            b = self._ap(Ln["b_ap"], x + self.g_dec * self.endA, ln["b_ap"] + mb, -self.g_dd1)
            Ln["b_d1"].put(b)
            b = Ln["b_d1"].at(ln["b_d1"] - 1.0)
            self.dampB += self.c_damp * (b - self.dampB)
            self.hpB += self.c_tlocut * (self.dampB - self.hpB)
            b = (self.dampB - self.hpB) * self.g_dec
            b = self._ap(Ln["b_ap2"], b, ln["b_ap2"], self.g_dd2)
            Ln["b_d2"].put(b)
            self.endA, self.endB = endA, Ln["b_d2"].at(ln["b_d2"] - 1.0)
            yl = 0.0
            for line, t, s in taps_l:
                yl += s * line.at(t)
            yr = 0.0
            for line, t, s in taps_r:
                yr += s * line.at(t)
            oL[i] = self.dry * L[i] + self.wet * 0.6 * yl
            oR[i] = self.dry * R[i] + self.wet * 0.6 * yr
        return oL, oR
