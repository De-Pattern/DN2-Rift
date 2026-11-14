"""RSNTR: a Roland P-6-style resonator as an insert (reference model).

The P-6's Resonator "uses Karplus-Strong synthesis ... a maximum of six resonators that match
different keys or chords", with ROOT, BRIGHT, FEEDBACK (0-99 %), CHORD (16 sets), PANNING and
ENV MOD ("larger values increase the amount of feedback according to the input level")
(P-6 Owner's Manual, Resonator). Made from that description and by ear, not from Roland's code.

Per voice and mono on the DN2, so PANNING has no place; KEYT (the strings follow the voice's
note) and DTUN, DRIV take its room. The panel (MIX on FX page 1):
    ROOT CHRD BRIT FDBK  /  ENVM KEYT DTUN DRIV
ROOT is a MIDI note (24..96), the rest 0..127.
"""
from __future__ import annotations

import math

import numpy as np

from .common import RATE, njit

CHORDS = {                       # semitones from ROOT, at most six strings
    "ROOT": (0,), "OCT": (0, 12), "UPDN": (-12, 0, 12), "P5": (0, 7, 12),
    "MIN": (0, 3, 7), "MAJ": (0, 4, 7), "MIN7": (0, 3, 7, 10), "MAJ7": (0, 4, 7, 11),
    "DOM7": (0, 4, 7, 10), "MIN9": (0, 3, 7, 10, 14), "MAJ9": (0, 4, 7, 11, 14),
    "MI11": (0, 3, 7, 10, 14, 17), "MA11": (0, 4, 7, 11, 14, 18), "SUS4": (0, 5, 7, 12),
    "DIM": (0, 3, 6, 9), "AUG": (0, 4, 8, 12),
}
CHORD_NAMES = tuple(CHORDS)
PAGE = ("ROOT", "CHRD", "BRIT", "FDBK", "ENVM", "KEYT", "DTUN", "DRIV")
DEFAULTS = dict(ROOT=48, CHRD=4, BRIT=80, FDBK=90, ENVM=40, KEYT=127, DTUN=10, DRIV=20, MIX=70)
MAXLEN = 4096                    # samples: down to about 12 Hz at 48 kHz


def params(**k) -> np.ndarray:
    v = {**DEFAULTS, **k}
    if isinstance(v["CHRD"], str):
        v["CHRD"] = CHORD_NAMES.index(v["CHRD"])
    return np.array([float(v[n]) for n in (*PAGE, "MIX")])


def _intervals() -> np.ndarray:
    t = np.full((len(CHORDS), 6), np.nan)
    for c, iv in enumerate(CHORDS.values()):
        t[c, :len(iv)] = iv
    return t


_IV = _intervals()


class Resonator:
    def __init__(self):
        self.lines = np.zeros((6, MAXLEN))
        self.f = np.zeros(6 * 3 + 4)          # per string: write index, lowpass, DC; then env, hp
        self.note = 60.0

    def process(self, x, p, note: float | None = None) -> np.ndarray:
        if note is not None:
            self.note = float(note)
        x = np.asarray(x, dtype=float).copy()
        _run(x, np.asarray(p, dtype=float), self.note, self.lines, self.f, _IV, RATE)
        return x


@njit(cache=True)
def _run(x, p, note, lines, f, iv, sr):
    root, chrd, brit, fdbk, envm, keyt, dtun, driv, mix = p
    c = int(chrd)
    base = root + (note - 60.0) * keyt / 127.0
    # FEEDBACK as a ring time: 0 -> 10 ms .. 127 -> 20 s (T60), each string's loop gain from its
    # own length, so a low string rings as long as a high one (a fixed gain per loop would not)
    t60 = 0.01 * 2000.0 ** (fdbk / 127.0)
    # BRIGHT: the loop's one-pole lowpass, its cutoff relative to the string (dark .. open)
    damp = 0.05 + 0.95 * (brit / 127.0) ** 0.7
    drive = 1.0 + driv / 127.0 * 6.0
    env_up, env_dn = 1.0 - math.exp(-1.0 / (0.002 * sr)), 1.0 - math.exp(-1.0 / (0.12 * sr))
    nstr = 0
    lens = np.zeros(6)
    for s in range(6):
        if iv[c, s] == iv[c, s]:                       # not nan
            spread = (s - 2.5) * dtun / 127.0 * 0.15       # up to +-0.4 semitone between strings
            fr = 440.0 * 2.0 ** ((base + iv[c, s] + spread - 69.0) / 12.0)
            fr = min(max(fr, sr / (MAXLEN - 4)), sr / 8.0)
            lens[s] = sr / fr
            nstr += 1
    norm = 1.0 / math.sqrt(max(nstr, 1))
    gs = np.zeros(6)
    for s in range(6):
        if lens[s] > 0.0:
            gs[s] = 10.0 ** (-3.0 * lens[s] / (sr * t60))
    E = 18
    for k in range(len(x)):
        xin = x[k]
        a = abs(xin)
        f[E] += (a - f[E]) * (env_up if a > f[E] else env_dn)
        boost = envm / 127.0 * min(f[E] * 2.0, 1.0)   # ENV MOD: a louder input, more feedback
        y = 0.0
        for s in range(6):
            L = lens[s]
            if L == 0.0:
                continue
            w = int(f[3 * s])
            rp = w - L
            while rp < 0.0:
                rp += MAXLEN
            i0 = int(rp)
            fr = rp - i0
            d = lines[s, i0 % MAXLEN] * (1.0 - fr) + lines[s, (i0 + 1) % MAXLEN] * fr
            lp = f[3 * s + 1] + (d - f[3 * s + 1]) * damp     # the loop's lowpass
            f[3 * s + 1] = lp
            g = min(gs[s] + boost * (0.9995 - gs[s]), 0.9995)
            v = xin * 2.0 + g * lp                     # struck hard: a short hit still rings
            v = math.tanh(v * drive * 0.5) / (drive * 0.5)   # always bounded: a string at its own pitch grows
            lines[s, w] = v
            f[3 * s] = (w + 1) % MAXLEN
            dc = f[3 * s + 2] + (v - f[3 * s + 2]) * 0.002   # a DC blocker on the string's output
            f[3 * s + 2] = dc
            y += v - dc
        x[k] = xin * (1.0 - mix / 127.0) + y * norm * mix / 127.0
