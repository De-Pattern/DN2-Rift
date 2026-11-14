"""FUNC: a function-generator envelope, after Make Noise Maths / Serge DUSG (reference model;
roadmap §2).

A rise and a fall, each through the same response curve (RESP: log ... linear ... exponential,
as Maths' Vari-Response), started by a note (or free, CYCLE), one-shot or looping. Looping, it
is an LFO whose shape is the two times and the curve; with a long fall and a short rise it is a
percussive envelope; with HOLD the rise waits at the top while the note is held (an AR).

Where it lives first (docs/fx-platform.md, roadmap §2): inside RIFT's own machines and
inserts as a modulation source on their controls, then, if the stock modulation routing can
take a fourth source, on the LFO pages. The panel when it has one of its own:
    RISE FALL RESP CYCL  /  HOLD DEST DEP  RETR
RISE and FALL 0..127 (0.5 ms .. 20 s), RESP 0..127 (64 linear, below log, above exponential),
CYCL off/on, HOLD off/on (sustain at the top while the note is held), RETR: a new note restarts
from 0 (on) or rises from where it is (off, as Maths). Output 0..1.
"""
from __future__ import annotations

import math

import numpy as np

from .common import RATE, njit

PAGE = ("RISE", "FALL", "RESP", "CYCL", "HOLD", "RETR")
DEFAULTS = dict(RISE=20, FALL=70, RESP=64, CYCL=0, HOLD=0, RETR=0)


def params(**k) -> np.ndarray:
    v = {**DEFAULTS, **k}
    return np.array([float(v[n]) for n in PAGE])


def seconds(v: float) -> float:
    return 0.0005 * 40000.0 ** (v / 127.0)


def shape(ph: float, resp: float) -> float:
    """The response curve on a phase 0..1: RESP 64 linear, 127 strongly exponential (slow
    start, fast end), 0 logarithmic (its mirror)."""
    return _shape(ph, resp)


@njit(cache=True)
def _shape(ph, resp):
    c = (resp - 64.0) / 63.0 * 6.0                   # -6 .. +6
    if abs(c) < 1e-6:
        return ph
    if c > 0.0:
        return (math.exp(c * ph) - 1.0) / (math.exp(c) - 1.0)
    c = -c
    return 1.0 - (math.exp(c * (1.0 - ph)) - 1.0) / (math.exp(c) - 1.0)


class FuncGen:
    def __init__(self):
        self.f = np.zeros(4)                         # phase, stage (0 idle, 1 rise, 2 hold, 3 fall), gate

    def process(self, n: int, p, gate=None) -> np.ndarray:
        """N samples of output; GATE (n) 1 while a note is held: a rise of it starts the rise."""
        g = np.zeros(n) if gate is None else np.asarray(gate, dtype=float)
        out = np.zeros(n)
        _run(out, np.asarray(p, dtype=float), g, self.f, RATE)
        return out


@njit(cache=True)
def _run(out, p, gate, f, sr):
    rise, fall, resp, cycl, hold, retr = p
    r_inc = 1.0 / max(0.0005 * 40000.0 ** (rise / 127.0) * sr, 1.0)
    f_inc = 1.0 / max(0.0005 * 40000.0 ** (fall / 127.0) * sr, 1.0)
    PH, ST, G = 0, 1, 2
    for n in range(len(out)):
        g = gate[n]
        if g > 0.5 and f[G] <= 0.5:                  # a note: rise (from 0, or from here)
            if retr > 63.0 or f[ST] == 0.0:
                f[PH] = 0.0
            elif f[ST] == 3.0:                       # Maths: rises from where the fall is
                f[PH] = f[PH]
            f[ST] = 1.0
        f[G] = g
        if f[ST] == 0.0 and cycl > 63.0:
            f[ST] = 1.0
        st = f[ST]
        if st == 1.0:
            f[PH] += r_inc
            if f[PH] >= 1.0:
                f[PH] = 1.0
                f[ST] = 2.0 if (hold > 63.0 and g > 0.5) else 3.0
        elif st == 2.0:
            if g <= 0.5:
                f[ST] = 3.0
        elif st == 3.0:
            f[PH] -= f_inc
            if f[PH] <= 0.0:
                f[PH] = 0.0
                f[ST] = 1.0 if cycl > 63.0 else 0.0
        out[n] = _shape(f[PH], resp)
