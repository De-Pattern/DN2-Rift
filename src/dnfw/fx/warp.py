"""WARP: a frequency shifter after the Tonverk's FREQUENCY WARPER (reference model).

The Tonverk manual (A.3.9): "A frequency-shifting effect in the style of vintage analog
effects", with SPD/DEP/SPH (a built-in LFO on the shift), LAG and SPRD (left/right offsets),
SHFT (the shift distance), SBND ("blends between the frequency shifter's output and an
alternate output signal with different characteristics") and MIX. Made from that text and by
ear: the Tonverk's update is encrypted, so none of its code is used.

A Bode-style shifter: a 90-degree allpass pair (Olli Niemitalo's 4+4 sections) and a
quadrature oscillator. SBND sweeps the upper sideband (0) through both, the ring modulator
(64), to the lower sideband (127). Mono per voice: LAG and SPRD wait for stereo, and FDBK
(the classic barber-pole feedback) and KEYT (the shift follows the voice's note, as a ratio)
take their places. The panel (MIX on FX page 1):
    SHFT SBND FDBK KEYT  /  SPD  DEP  SPH  RANG
SHFT is bipolar (64 = none); RANG: 0 fine (+-50 Hz) .. 127 wide (+-5 kHz).
"""
from __future__ import annotations

import math

import numpy as np

from .common import RATE, njit

PAGE = ("SHFT", "SBND", "FDBK", "KEYT", "SPD", "DEP", "SPH", "RANG")
DEFAULTS = dict(SHFT=80, SBND=0, FDBK=0, KEYT=0, SPD=40, DEP=0, SPH=0, RANG=64, MIX=100)
_A = np.array([0.6923878, 0.9360654322959, 0.9882295226860, 0.9987488452737]) ** 2
_B = np.array([0.4021921162426, 0.8561710882420, 0.9722909545651, 0.9952884791278]) ** 2


def params(**k) -> np.ndarray:
    v = {**DEFAULTS, **k}
    return np.array([float(v[n]) for n in (*PAGE, "MIX")])


def shift_hz(shft: float, rang: float) -> float:
    """SHFT's distance in Hz: bipolar, exponential, from +-(50 Hz .. 5 kHz) by RANG."""
    b = (shft - 64.0) / 63.0
    top = 50.0 * 100.0 ** (rang / 127.0)
    return math.copysign(top * (abs(b) ** 2.2), b)


class Warp:
    def __init__(self):
        self.f = np.zeros(4 * 4 + 8)        # 2 paths x 4 sections x (x1 x2 y1 y2) ... and the rest
        self.ap = np.zeros((2, 4, 4))
        self.note = 60.0

    def process(self, x, p, note: float | None = None, note_on=()) -> np.ndarray:
        if note is not None:
            self.note = float(note)
        x = np.asarray(x, dtype=float).copy()
        on = np.zeros(len(x), dtype=np.int64)
        for k in note_on:
            if 0 <= k < len(x):
                on[k] = 1
        hz = shift_hz(p[0], p[7])
        _run(x, np.asarray(p, dtype=float), hz, self.note, on, self.ap, self.f, _A, _B, RATE)
        return x


@njit(cache=True)
def _ap(st, coef, v):
    for s in range(4):
        x1, x2, y1, y2 = st[s, 0], st[s, 1], st[s, 2], st[s, 3]
        y = coef[s] * (v + y2) - x2
        st[s, 0], st[s, 1], st[s, 2], st[s, 3] = v, x1, y, y1
        v = y
    return v


@njit(cache=True)
def _run(x, p, hz, note, on, ap, f, A, B, sr):
    shft, sbnd, fdbk, keyt, spd, dep, sph, rang, mix = p
    # KEYT: the shift scales with the note (a ratio of the voice's pitch)
    hz = hz * 2.0 ** ((note - 60.0) * keyt / 127.0 / 12.0)
    lfo_hz = 0.02 * 1000.0 ** (spd / 127.0)            # 0.02 .. 20 Hz
    lfo_dep = (dep / 127.0) ** 2 * max(abs(hz), 5.0) * 2.0
    up = min(max(1.0 - sbnd / 64.0, 0.0), 1.0)
    dn = min(max((sbnd - 64.0) / 63.0, 0.0), 1.0)
    mid = 1.0 - up - dn                                # the ring modulator's share
    g = fdbk / 127.0 * 0.9
    PH, LF, DL, FB = 16, 17, 18, 19
    for k in range(len(x)):
        if on[k] and sph > 0.0:                        # SPH: the LFO restarts at its phase on a note
            f[LF] = (sph - 1.0) / 126.0
        f[LF] += lfo_hz / sr
        if f[LF] >= 1.0:
            f[LF] -= 1.0
        lfo = math.sin(2.0 * math.pi * f[LF])
        h = hz + lfo * lfo_dep
        v = x[k] + f[FB] * g
        i_ = _ap(ap[0], A, v)
        q = f[DL]
        f[DL] = _ap(ap[1], B, v)
        f[PH] += h / sr
        f[PH] -= math.floor(f[PH])
        c, s = math.cos(2.0 * math.pi * f[PH]), math.sin(2.0 * math.pi * f[PH])
        usb, lsb = i_ * c + q * s, i_ * c - q * s
        y = up * usb + dn * lsb + mid * (i_ * c)       # mid: both sidebands at half, a ring modulator
        f[FB] = math.tanh(y)
        x[k] = x[k] * (1.0 - mix / 127.0) + y * mix / 127.0
