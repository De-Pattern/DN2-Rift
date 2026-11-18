"""RESONATOR's voice on the SHARC's arithmetic (float32, FASCIA's `recip` for every divide, Ravel's
rv_math.h leaves): the SHARC program's contract (dnfw.reson.program, bit-exact, test_reson_program).

RESONATOR comes back from the DN2 mk2 mod's early versions (v0.6-v0.25, `docs/rings.md` there; owner,
2026-11-17: "add the old resonator machine back to this firmware"): a Rings-style MODAL resonator,
24 two-pole modes a voice, struck by a mallet blended with a noise burst. The sound is that machine's
(its model and constants), rebuilt the RIFT way: a machine in FASCIA's walk (type 22), its eight
controls on FASCIA's records (organ.live.RIDES' first eight), the coefficients from Ravel's leaves once
a block rather than the old tables, the noise from a xorshift rather than W2's random table.

**Controls** (knobs 0..127):

| control | here |
|---|---|
| TUNE | k - 64 semitones (shown -64..+63) |
| LEV  | k / 100: 1.0 at 100 |
| STRC | k / 127: 0 harmonic (a string), 0.5 a bar (marimba), 1 a plate / bell |
| BRIT | 0.15 + 0.8 k / 127: the mallet's width, and how much faster high modes die |
| DAMP | T60 0.1 s .. 12 s |
| POS  | 0.02 + 0.48 k / 127: where it is hit (the middle mutes every other mode) |
| EXCT | k / 127: MALLET <- blend -> NOISE |
| HIT  | k / 100: how hard it is hit, 1.0 at 100 |

**The voice.** A trig restarts the exciter into the modes; mode n rings y = a1 y1 - a2 y2 + b0 x with
a1 = 2 R cos w, a2 = R^2, b0 = amp_n sin w; R from the mode's T60 (high modes shorter, by BRIT), amp_n
from POS (sin(pi n POS)) and a tilt by BRIT. Modes at or above note 135 (19.9 kHz) are left out. The sum,
normalised by the modes' summed level and by pitch, passes PING's output knee. A voice whose hit is done
and whose block peaked under IDLE rests (it costs nothing until its next note).
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, recip, exp2f, expf, sin_turns, note_hz, xs_bi, DT

SUB = 32
MODES = 24
TOP_NOTE = F(135.0)
IDLE = F(1.0e-5)
OUT_GAIN = F(0.12)
NORM = F(0.25)
NOISE_LEN = 576                               # 12 ms
NOISE_DECAY = F(np.exp(-1.0 / (NOISE_LEN / 4)))
EXC_END = 1024                                # the exciter is silent from here (the mallet ends by 403)
MAGIC = 0x52534E21                            # 'RSN!': the voice's state was written by a strike
TRIM = F(1.0)
INV127 = F(F(1.0) / F(127.0))
INV100 = F(F(1.0) / F(100.0))
INV12 = F(F(1.0) / F(12.0))
L_DAMP0 = F(np.log2(6.91 / 4800.0))          # log2(-ln R) for a T60 of 0.1 s at 48 kHz ...
L_DAMP1 = F(np.log2(120.0))                  # ... down to 12 s
KNEE_K, KNEE_ROOM = F(0.6), F(0.6)
GUARD = F(65536.0)                            # a mode sum past this has blown up: the voice rests

CONTROLS = ("TUNE", "LEV", "STRC", "BRIT", "DAMP", "POS", "EXCT", "HIT")
DEFAULTS = {"TUNE": 64, "LEV": 100, "STRC": 0, "BRIT": 127, "DAMP": 110, "POS": 64, "EXCT": 64, "HIT": 100}


def anchors() -> np.ndarray:
    """3 x 24 semitone offsets of the modes: harmonic, a free bar, a plate (the old machine's)"""
    n = range(1, MODES + 1)
    harmonic = [float(k) for k in n]
    bar = [((2 * k + 1) / 3.0) ** 2 for k in n]
    bar = [b / bar[0] for b in bar]
    plate = [1.0, 1.594, 2.136, 2.296, 2.653, 2.918, 3.156, 3.501, 3.600, 4.060, 4.154,
             4.601, 4.832, 5.131, 5.412, 5.651, 5.937, 6.164, 6.415, 6.749, 6.976, 7.244,
             7.470, 7.735]
    return np.array([[F(12.0 * np.log2(r)) for r in a] for a in (harmonic, bar, plate)], dtype=np.float32)


ANCH = anchors()


def knee(x):
    a = F(abs(x))
    if a <= KNEE_K:
        return F(x)
    o = min(F(a - KNEE_K), KNEE_ROOM)
    y = F(KNEE_K + F(o - F(F(o * o) * F(F(0.5) / KNEE_ROOM))))
    return y if x > 0 else F(-y)


class Controls:
    __slots__ = ("pitch", "frac", "a0", "l0", "kexp", "pos", "mix", "hit", "lev", "tilt_g", "minc", "mnorm",
                 "nlp_a")


def controls(knobs, note) -> Controls:
    k = {c: int(v) for c, v in zip(CONTROLS, knobs)}
    c = Controls()
    tun = F(k["TUNE"] - 64)
    c.pitch = min(max(F(F(note) + tun), F(0.0)), F(127.0))
    st = F(F(k["STRC"]) * INV127)
    b = F(F(0.15) + F(F(0.8) * F(F(k["BRIT"]) * INV127)))
    kd = F(F(k["DAMP"]) * INV127)
    c.l0 = F(L_DAMP0 - F(kd * L_DAMP1))
    c.kexp = F(F(F(F(1.0) - b) * F(1.3)) + F(0.2))
    c.pos = F(F(0.02) + F(F(0.48) * F(F(k["POS"]) * INV127)))
    c.mix = F(F(k["EXCT"]) * INV127)
    c.hit = F(F(k["HIT"]) * INV100)
    c.lev = F(F(k["LEV"]) * INV100)
    if st <= F(0.5):
        c.frac, c.a0 = F(st * F(2.0)), 0
    else:
        c.frac, c.a0 = F(F(st * F(2.0)) - F(1.0)), 1
    c.tilt_g = F(F(0.6) + F(F(0.4) * b))
    d = F(F(1.0) - b)
    width = F(F(0.0004 * 48000) + F(F(0.008 * 48000) * F(d * d)))
    rw = recip(width)
    c.minc = F(F(0.5) * rw)                   # the mallet's phase a sample, in turns (half a turn long)
    c.mnorm = min(F(F(24.0) * rw), F(1.0))
    c.nlp_a = min(F(F(F(F(b * b) * F(12000.0)) + F(300.0)) * F(F(6.28318530717958647692) * DT)), F(1.0))
    return c


def coefs(c: Controls):
    """[(a1, a2, b0)] of each mode that sounds, low to high, and the sum of their |amp|"""
    out = []
    asum = F(0.0)
    tilt = F(1.0)
    for n in range(MODES):
        lo, hi = ANCH[c.a0][n], ANCH[c.a0 + 1][n]
        semi = F(lo + F(c.frac * F(hi - lo)))
        q = F(c.pitch + semi)
        if q >= TOP_NOTE:
            break
        ft = F(note_hz(q) * DT)                # w in turns
        cw, sw = sin_turns(F(ft + F(0.25))), sin_turns(ft)
        L = F(c.l0 + F(c.kexp * F(semi * INV12)))
        R = expf(F(F(0.0) - exp2f(L)))
        amp = F(sin_turns(F(F(F(n + 1) * c.pos) * F(0.5))) * tilt)
        out.append((F(F(2.0) * F(R * cw)), F(R * R), F(amp * sw)))
        asum = F(asum + F(abs(amp)))
        tilt = F(tilt * c.tilt_g)
    return out, asum


class Voice:
    """one slot's RESONATOR voice, block by block (a trig strikes it: the modes keep ringing, as a struck
    bar does; FASCIA's walk fades a stolen voice)"""

    def __init__(self, slot: int = 0):
        self.slot = slot
        self.y1 = np.zeros(MODES, dtype=np.float32)
        self.y2 = np.zeros(MODES, dtype=np.float32)
        self.on = 0
        self.exc = 0
        self.nenv = F(0.0)
        self.nlp = F(0.0)
        self.rng = [0x2545F491 + slot]
        self.note = F(0.0)                      # the note, latched at the trig

    def block(self, knobs, trig: bool, note: float, vel: int = 127) -> np.ndarray:
        if trig:
            self.on, self.exc, self.nenv, self.nlp = 1, 0, F(1.0), F(0.0)
            self.note = F(note)
        if not self.on:
            return np.zeros(SUB, dtype=np.float32)
        c = controls(knobs, self.note)
        x = np.zeros(SUB, dtype=np.float32)
        for i in range(SUB):
            if self.exc >= EXC_END:
                break
            ph = F(F(self.exc) * c.minc)
            mal = F(sin_turns(ph) * c.mnorm) if ph < F(0.5) else F(0.0)
            nz = xs_bi(self.rng)
            if self.exc < NOISE_LEN:
                nz = F(nz * self.nenv)
                self.nenv = F(self.nenv * NOISE_DECAY)
            else:
                nz = F(0.0)
            self.nlp = F(self.nlp + F(c.nlp_a * F(nz - self.nlp)))
            xx = F(F(F(F(1.0) - c.mix) * mal) + F(c.mix * F(F(0.5) * self.nlp)))
            x[i] = F(xx * c.hit)
            self.exc += 1
        acc = np.zeros(SUB, dtype=np.float32)
        cf, asum = coefs(c)
        for m, (a1, a2, b0) in enumerate(cf):
            y1, y2 = self.y1[m], self.y2[m]
            for i in range(SUB):
                y = F(F(F(a1 * y1) - F(a2 * y2)) + F(b0 * x[i]))
                y2, y1 = y1, y
                acc[i] = F(acc[i] + y)
            self.y1[m], self.y2[m] = y1, y2
        for m in range(len(cf), MODES):         # a mode past the top rests
            self.y1[m] = self.y2[m] = F(0.0)
        if not all(-GUARD < a < GUARD for a in acc):     # blown up (or not finite): the voice rests
            self.__init__(self.slot)
            return np.zeros(SUB, dtype=np.float32)
        tilt_p = exp2f(F(F(c.pitch - F(60.0)) * F(1.0 / 24.0)))
        g = F(F(F(c.lev * OUT_GAIN) * recip(F(F(1.0) + F(NORM * asum)))) * tilt_p)
        out = np.array([knee(F(a * g)) for a in acc], dtype=np.float32)
        peak = F(0.0)
        for a in acc:
            peak = max(peak, F(abs(a)))
        if self.exc >= EXC_END and peak < IDLE:
            self.on = 0
            self.y1[:] = 0
            self.y2[:] = 0
        return out
