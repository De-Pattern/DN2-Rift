"""CHRONO: a granular pitch shifter after the Tonverk's CHRONO PITCH (reference model).

The Tonverk manual (A.3.2): "A granular pitch shifter with modulation and feedback": TUNE
(semitones), WIN (window, the grain size), FDBK, DEP and SPD (a built-in LFO on the pitch),
HPF and LPF on the wet signal, MIX. Made from that text and by ear (the Tonverk's update is
encrypted, so none of its code is used).

Two grains read a delay line at 2^(TUNE/12) speed, half a window apart, each under a sine
window, so their sum is steady; the wet sound feeds back into the line through FDBK, which
stacks the shift (a shimmer up, a spiral down). JITR moves each grain's start a little at
random, which smooths the window's buzz on sustained tones. The panel (MIX on FX page 1):
    TUNE WIN  FDBK DEP  /  SPD  HPF  LPF  JITR
TUNE is bipolar, 64 = 0, +-24 semitones in whole steps.
"""
from __future__ import annotations

import math

import numpy as np

from .common import RATE, njit, xorshift

PAGE = ("TUNE", "WIN", "FDBK", "DEP", "SPD", "HPF", "LPF", "JITR")
DEFAULTS = dict(TUNE=76, WIN=60, FDBK=0, DEP=0, SPD=40, HPF=0, LPF=127, JITR=20, MIX=100)
LINE = 32768                                  # 680 ms at 48 kHz: a 120 ms window two octaves up


def params(**k) -> np.ndarray:
    v = {**DEFAULTS, **k}
    return np.array([float(v[n]) for n in (*PAGE, "MIX")])


def semitones(tune: float) -> float:
    return float(round((tune - 64.0) * 24.0 / 63.0))


class Chrono:
    def __init__(self, seed: int = 0x2545F491):
        self.line = np.zeros(LINE)
        self.f = np.zeros(12)
        self.i = np.array([0, seed & 0xFFFFFFFF], dtype=np.int64)
        self.started = False

    def process(self, x, p) -> np.ndarray:
        x = np.asarray(x, dtype=float).copy()
        if not self.started:
            start(self, p[1])
            self.started = True
        _run(x, np.asarray(p, dtype=float), semitones(p[0]), self.line, self.f, self.i, RATE)
        return x


@njit(cache=True)
def _run(x, p, semis, line, f, i, sr):
    tune, win, fdbk, dep, spd, hpf, lpf, jitr, mix = p
    W = int((0.005 + 0.115 * (win / 127.0) ** 1.5) * sr)          # 5 .. 120 ms
    g = fdbk / 127.0 * 0.92
    lfo_hz = 0.05 * 400.0 ** (spd / 127.0)                         # 0.05 .. 20 Hz
    lfo_semi = (dep / 127.0) ** 2 * 1.0                            # up to a semitone
    hp_c = 1.0 - math.exp(-2.0 * math.pi * (20.0 * 100.0 ** (hpf / 127.0)) / sr) if hpf > 0 else 0.0
    lp_c = 1.0 - math.exp(-2.0 * math.pi * (200.0 * 100.0 ** (lpf / 127.0)) / sr)
    PH0, LF, HP, LP, J0, J1 = 0, 2, 3, 4, 5, 6
    for k in range(len(x)):
        f[LF] += lfo_hz / sr
        if f[LF] >= 1.0:
            f[LF] -= 1.0
        rate = 2.0 ** ((semis + lfo_semi * math.sin(2.0 * math.pi * f[LF])) / 12.0)
        w = i[0]
        # each grain's age runs 0..W; its read point trails the write by (1 - rate) * age + a guard
        y = 0.0
        for gi in range(2):
            ph = f[PH0 + gi]
            if ph >= W:
                ph -= W
                s, v = xorshift(i[1])
                i[1] = s
                f[J0 + gi] = (v >> 8) * (1.0 / 16777216.0) * jitr / 127.0 * W * 0.5
            age = ph
            delay = 2.0 + f[J0 + gi] + max(rate - 1.0, 0.0) * W - age * (rate - 1.0)
            rp = w - delay
            while rp < 0.0:
                rp += LINE
            i0 = int(rp)
            fr = rp - i0
            d = line[i0 % LINE] * (1.0 - fr) + line[(i0 + 1) % LINE] * fr
            y += d * math.sin(math.pi * age / W)
            f[PH0 + gi] = ph + 1.0
        y *= 0.7071                                                 # two sine windows: power-steady
        f[LP] += (y - f[LP]) * lp_c
        y = f[LP]
        if hp_c > 0.0:
            f[HP] += (y - f[HP]) * hp_c
            y = y - f[HP]
        line[w] = x[k] + math.tanh(y * g) if g > 0.0 else x[k]
        i[0] = (w + 1) % LINE
        x[k] = x[k] * (1.0 - mix / 127.0) + y * mix / 127.0
    return


def start(ch: Chrono, win: float) -> None:
    """Grain 2 half a window behind grain 1, as they run."""
    W = int((0.005 + 0.115 * (win / 127.0) ** 1.5) * RATE)
    ch.f[0], ch.f[1] = 0.0, W / 2.0
