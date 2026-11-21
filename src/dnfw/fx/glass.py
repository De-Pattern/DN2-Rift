"""GLASS: a new FLTR type, reference model (owner, 2026-11-21: "a serge vcfq style filter ... high
resonance without sounding clippy or distorted or whiny. a more rounded, glassy sound thats great for
very hard, POPPING transient sounds to ping ... like tapping a wine glass with a screwdriver ... a
state variable filter like the Multi-Mode ... not lose much low end with high resonance").

The core: a state-variable filter in the topology-preserving (zero-delay-feedback) form, run at
twice the rate (each sample: two steps, the input held), so it tracks its cutoff up to the top and
stays stable at any resonance, its pole radius exactly where RES puts it.

What makes it GLASS and not the Multi-Mode:
- **A soft limit inside the loop, not after it.** The band-pass state passes through a gentle
  odd curve (x / sqrt(1 + (x/L)^2)) before it feeds back: below L the filter is linear and pure; a
  hard hit's ringing is held to about L, rounded, never clipped. So a ping rings as a clean sine
  that decays, the glass, however hard the strike.
- **The low end kept.** As RES rises, the input into the loop is eased (its energy otherwise goes
  into the ringing and the limit squashes the bass), and the low-pass output gets back a share of
  the input's lows below the cutoff (a one-pole at the cutoff), RES-scaled, so the bass under a
  ringing peak stays where it was at RES 0.
- **A ring that can be played.** RES at its top: the decay of a ping is several seconds, its pitch
  the cutoff's, so a hard transient through it is a struck tuned glass; the envelope sweeps it.

Modes (the Multi-Mode's): LP, BP, HP, and the LP/BP/HP morph of TYPE (0 LP, 0.5 BP, 1 HP).

The envelope: the stock ATK DEC SUS REL, with ATK BEND and DEC BEND (-1 exponential, 0 the stock's
curve, +1 logarithmic), into cutoff by ENV DEPTH. LPG: the filter and a VCA closed together by a
vactrol-like contour (a fast rise; a fall that slows as it closes), for bongo-like decays.
"""
from __future__ import annotations

import math

import numpy as np

RATE = 48000.0


def _soft(x: float, lim: float) -> float:
    return x / math.sqrt(1.0 + (x / lim) * (x / lim))


class Glass:
    def __init__(self, cutoff=1000.0, res=0.7, mode=0.0, lim=0.6, keep_low=True):
        self.s1 = self.s2 = 0.0
        self.lowz = 0.0
        self.set(cutoff, res, mode, lim, keep_low)

    def set(self, cutoff, res, mode=None, lim=None, keep_low=None):
        self.cutoff = min(max(cutoff, 16.0), 22000.0)
        self.res = min(max(res, 0.0), 1.0)
        if mode is not None:
            self.mode = mode
        if lim is not None:
            self.lim = lim
        if keep_low is not None:
            self.keep_low = keep_low
        fs2 = 2.0 * RATE
        self.g = math.tan(math.pi * min(self.cutoff, 0.45 * fs2) / fs2)
        # RES is the ring's length, the same at every cutoff (a glass rings as long high as low):
        # its time constant 4 ms (RES 0) to 4 s (RES 1); Q = pi f tau, never under 0.5
        tau = 0.004 * 1000.0 ** (self.res ** 1.3)
        q = max(0.5, math.pi * self.cutoff * tau)
        self.k = 1.0 / q
        self.a1 = 1.0 / (1.0 + self.g * (self.g + self.k))
        self.drive = 1.0 - 0.45 * self.res ** 2           # the input eased as RES rises
        self.lp1 = 1.0 - math.exp(-2.0 * math.pi * self.cutoff / RATE)

    def tick(self, x: float) -> float:
        xin = x * self.drive
        lp = bp = hp = 0.0
        for _ in range(2):                                # twice the rate, the input held
            v3 = xin - self.s2
            v1 = self.a1 * (self.s1 + self.g * v3)
            v2 = self.s2 + self.g * v1
            self.s1 = _soft(2.0 * v1 - self.s1, self.lim * 2.0)
            self.s2 = 2.0 * v2 - self.s2
            lp, bp = v2, v1
            hp = xin - self.k * v1 - v2
        lp /= self.drive
        bp /= self.drive
        hp /= self.drive
        if self.keep_low:                                 # the bass under the peak, as at RES 0
            self.lowz += self.lp1 * (x - self.lowz)
            lp = lp + 0.5 * self.res * (self.lowz - lp) * (1.0 if self.res > 0.3 else self.res / 0.3)
        m = self.mode
        if m <= 0.5:
            t = m / 0.5
            return (1 - t) * lp + t * bp * self.k * 2.0 ** 0.5
        t = (m - 0.5) / 0.5
        return (1 - t) * bp * self.k * 2.0 ** 0.5 + t * hp


def bend(u: float, b: float) -> float:
    """a 0..1 segment shaped by BEND -1..+1: -1 exponential (slow then fast), 0 linear, +1 log"""
    if abs(b) < 1e-6:
        return u
    k = 6.0 * abs(b)
    if b < 0:
        return (math.exp(k * u) - 1.0) / (math.exp(k) - 1.0)
    return math.log1p((math.exp(k) - 1.0) * u) / k


def envelope(n: int, atk: float, dec: float, sus: float, rel: float, gate: int, ab=0.0, db=0.0):
    """ATK, DEC, REL in seconds; SUS 0..1; GATE samples held; AB, DB the bends"""
    out = np.zeros(n)
    a, d, r = max(1, int(atk * RATE)), max(1, int(dec * RATE)), max(1, int(rel * RATE))
    lvl = 0.0
    for i in range(n):
        if i < gate:
            if i < a:
                lvl = bend(i / a, ab)
            elif i < a + d:
                lvl = 1.0 - (1.0 - sus) * bend((i - a) / d, db)
            else:
                lvl = sus
            held = lvl
        else:
            j = i - gate
            lvl = held * (1.0 - bend(min(1.0, j / r), db))
        out[i] = lvl
    return out


def vactrol(n: int, hits: list[int], vel=1.0, fall=0.25):
    """LPG: a fast rise (2 ms) at each hit, then a fall that slows as it closes (a vactrol's)"""
    out = np.zeros(n)
    lvl = 0.0
    hs = set(hits)
    rise = 1.0 - math.exp(-1.0 / (0.002 * RATE))
    target = 0.0
    for i in range(n):
        if i in hs:
            target = vel
        if target > lvl:
            lvl += rise * (target - lvl)
            if lvl > 0.98 * target:
                target = 0.0
        else:
            tau = fall * (0.15 + 0.85 * (1.0 - lvl) ** 2) * 4.0   # slower as it closes
            lvl *= math.exp(-1.0 / (tau * RATE))
        out[i] = lvl
    return out


def run(x: np.ndarray, cutoff, res, mode=0.0, env=None, depth=0.0, lpg=None, lim=0.6, keep_low=True):
    """CUTOFF in Hz (or an array a sample); ENV 0..1 a sample, DEPTH in octaves; LPG a vactrol
    contour (the cutoff and the level both follow it)"""
    f = Glass(float(np.atleast_1d(cutoff)[0]), res, mode, lim, keep_low)
    y = np.zeros(len(x))
    for i in range(len(x)):
        c = float(cutoff[i]) if np.ndim(cutoff) else cutoff
        if env is not None:
            c *= 2.0 ** (depth * env[i])
        if lpg is not None:
            c = 40.0 + (c - 40.0) * lpg[i] ** 1.5
        if i % 8 == 0:
            f.set(c, res)
        v = f.tick(float(x[i]))
        y[i] = v * (lpg[i] ** 1.2 if lpg is not None else 1.0)
    return y


class SVF:
    """the reference: a plain (Chamberlin) state-variable low-pass, as most hardware SVFs, a hard
    clip after it: for comparison only"""
    def __init__(self, cutoff, res):
        self.l = self.b = 0.0
        self.f = 2.0 * math.sin(math.pi * min(cutoff, 8000) / RATE)
        self.q = 2.0 - 1.98 * res

    def tick(self, x):
        self.l += self.f * self.b
        h = x - self.l - self.q * self.b
        self.b += self.f * h
        return max(-1.0, min(1.0, self.l))
