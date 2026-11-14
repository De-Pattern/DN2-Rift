"""LPG: a low-pass gate as a new filter type (reference model; roadmap §3).

Not an insert: a real filter type on the FLTR page, beside Multi-Mode, Lowpass 4 and the rest,
for any machine. A Buchla 292-style vactrol gate: the filter envelope lights the vactrol's LED,
and the vactrol (a fast rise, a slow fall that slows further as it darkens, from the DN2 mk2
mod's PING model) opens the cutoff and the level together, so a note dies darker as it dies
quieter: the "bongo".

It takes the stock filter page as it is (the DN2's filter envelope is ADSR + depth):
    ATK  DEC  SUS  REL  /  FREQ RESO TYPE ENV
- FREQ: the cutoff when the gate is fully open (with key tracking from the stock page 2);
- RESO: a resonance the 292 lacks, for the ringing, struck sound (PING's damping law);
- TYPE: the 292's mode switch: COMBO (cutoff and level), LP (cutoff only), VCA (level only);
- ENV: how far the envelope opens the gate (0: always fully open, a plain low-pass).
Values 0..127 as the stock page's.
"""
from __future__ import annotations

import math

import numpy as np

from .common import RATE, njit

TYPES = ("COMBO", "LP", "VCA")
PAGE = ("ATK", "DEC", "SUS", "REL", "FREQ", "RESO", "TYPE", "ENV")
DEFAULTS = dict(ATK=0, DEC=50, SUS=0, REL=40, FREQ=110, RESO=20, TYPE=0, ENV=127)


def params(**k) -> np.ndarray:
    v = {**DEFAULTS, **k}
    if isinstance(v["TYPE"], str):
        v["TYPE"] = TYPES.index(v["TYPE"])
    return np.array([float(v[n]) for n in PAGE])


def seconds(v: float) -> float:
    """The stock envelope's time curve, roughly: 0 -> 1 ms .. 127 -> 10 s."""
    return 0.001 * 10000.0 ** (v / 127.0)


class LPG:
    def __init__(self):
        self.f = np.zeros(6)          # env, stage, vactrol, svf ic1, ic2, (spare)

    def process(self, x, p, gate) -> np.ndarray:
        """GATE: 1 while the note is held, 0 after; a rise starts the envelope."""
        x = np.asarray(x, dtype=float).copy()
        _run(x, np.asarray(p, dtype=float), np.asarray(gate, dtype=float), self.f, RATE)
        return x


@njit(cache=True)
def _run(x, p, gate, f, sr):
    atk, dec, sus, rel, freq, reso, typ, env = p
    t = int(typ)
    a_rate = 1.0 / max(0.001 * 10000.0 ** (atk / 127.0) * sr, 1.0)
    d_coef = math.exp(-1.0 / (0.001 * 10000.0 ** (dec / 127.0) * sr))
    r_coef = math.exp(-1.0 / (0.001 * 10000.0 ** (rel / 127.0) * sr))
    s_lvl = sus / 127.0
    fmax = 30.0 * 2.0 ** (freq / 127.0 * 9.5)            # 30 Hz .. about 22 kHz
    depth = env / 127.0
    rise = 1.0 - math.exp(-1.0 / (0.0008 * sr))
    k_res = 2.0 - 1.95 * (reso / 127.0) ** 0.6            # the SVF's damping: 2 (none) .. 0.05
    E, ST, V, I1, I2, G0 = 0, 1, 2, 3, 4, 5
    for n in range(len(x)):
        g_in = gate[n]
        if g_in > 0.5 and f[G0] <= 0.5:
            f[ST] = 1.0                                   # attack
        f[G0] = g_in
        if f[ST] == 1.0:
            f[E] += a_rate
            if f[E] >= 1.0:
                f[E], f[ST] = 1.0, 2.0
        elif f[ST] == 2.0:
            f[E] = s_lvl + (f[E] - s_lvl) * d_coef
            if g_in <= 0.5:
                f[ST] = 3.0
        else:
            f[E] *= r_coef
        led = 1.0 - depth + depth * f[E]
        v = f[V]
        if led > v:
            v += (led - v) * rise
        else:
            tau = 0.04 * (0.35 + 1.3 * (1.0 - v)) + 0.6 * (1.0 - v) ** 3 * (rel / 127.0)
            v += (led - v) * (1.0 - math.exp(-1.0 / (max(tau, 0.001) * sr)))
        f[V] = v
        fc = 30.0 * (fmax / 30.0) ** v if t != 2 else fmax
        fc = min(fc, 0.45 * sr)
        g = math.tan(math.pi * fc / sr)
        # a TPT state-variable low-pass
        a1 = 1.0 / (1.0 + g * (g + k_res))
        v1 = (f[I1] + g * (x[n] - f[I2])) * a1
        v2 = f[I2] + g * v1
        f[I1], f[I2] = 2.0 * v1 - f[I1], 2.0 * v2 - f[I2]
        y = v2
        amp = v ** 1.4 if t != 1 else 1.0
        y = math.tanh(y * amp * 1.2) / 1.2
        x[n] = y
