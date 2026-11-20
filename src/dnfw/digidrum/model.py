"""DIGIDRUM's design model (float64, per sample): six digital drum voices after the Syntakt's
digital machines (manual OS 1.42, appendix A.2), by their documented controls and by ear. Not
Elektron's code: our own synthesis for each control's described behaviour. Chosen by ear first
(scripts/digidrum_audition.py); then a float32 live model and the SHARC program, as RIFT's other
machines.

Every type shares TUNE (semitones, bipolar), PNCH (a compressor-like accent envelope that also
drives the sound), DEC (the amp decay) and OVER (a digital overdrive); each has its own four.
"""
from __future__ import annotations

import math

import numpy as np

FS = 48000
TYPES = ("BD MODERN", "SD BASIC", "SD VINTAGE", "CP VINTAGE", "CY ALLOY", "PC CARBON")
# the four type-specific controls (between DEC and OVER), the Syntakt's names
OWN = {"BD MODERN": ("SWEP", "SMOD", "TMOD", "MENV"),
       "SD BASIC": ("SWEP", "INHM", "MDFB", "MENV"),
       "SD VINTAGE": ("SWEP", "INHM", "FCMP", "MENV"),
       "CP VINTAGE": ("SPCR", "BAL", "BODY", "BENV"),
       "CY ALLOY": ("SHIM", "RADIO", "MOD", "MENV"),
       "PC CARBON": ("SWEP", "INHM", "MOD", "MENV")}
BASE_NOTE = {"BD MODERN": 31, "SD BASIC": 50, "SD VINTAGE": 50, "CP VINTAGE": 60, "CY ALLOY": 72, "PC CARBON": 60}


def mtof(n):
    return 440.0 * 2.0 ** ((n - 69.0) / 12.0)


def env(n, t60):
    """exp decay to -60 dB in T60 seconds"""
    t = np.arange(n) / FS
    return np.exp(-6.9078 * t / max(t60, 1e-4))


def punch(y, k):
    """PNCH: an accent envelope (a fast attack gain bump) and drive into a soft clip"""
    if k <= 0:
        return y
    n = len(y)
    t = np.arange(n) / FS
    bump = 1.0 + 2.5 * k * np.exp(-t / 0.035)
    return np.tanh(y * bump * (1 + 2 * k)) / np.tanh(1 + 2 * k)


def over(y, k):
    if k <= 0:
        return y
    g = 1 + 20 * k * k
    return np.tanh(y * g) / math.tanh(g) ** 0.5


def render(type_, note=None, vel=1.0, secs=1.2, **kn):
    """KN: knobs 0..127 by name (TUNE 64 = 0); -> mono float array"""
    k = {c: kn.get(c, 64) / 127.0 for c in ("TUNE", "PNCH", "DEC", "OVER", *OWN[type_])}
    k["PNCH"] = kn.get("PNCH", 30) / 127.0
    k["OVER"] = kn.get("OVER", 0) / 127.0
    k["TUNE"] = (kn.get("TUNE", 64) - 64)
    n = int(secs * FS)
    t = np.arange(n) / FS
    note = (BASE_NOTE[type_] if note is None else note) + k["TUNE"]
    f0 = mtof(note)
    dec = 0.02 * 2 ** (k["DEC"] * 9)                 # 20 ms .. 10 s
    rng = np.random.default_rng(7)
    if type_ == "BD MODERN":
        # v2 (owner, 2026-11-18: "not as deep"): a lower base (G0, 49 Hz), a sweep that starts
        # higher and lands slower, the modulation scaled down at its defaults (it thinned the
        # body), a sub sine under the body, and a short click
        sw = k["SWEP"]
        sweep = 1 + 9 * sw * np.exp(-t / (0.006 + 0.07 * sw))
        ph = 2 * np.pi * np.cumsum(f0 * sweep) / FS
        me = np.exp(-t / (0.004 + 0.3 * k["MENV"])) * (0.2 + 0.8 * k["MENV"])
        sq = np.sign(np.sin(ph * 2)) * (k["SMOD"] ** 2) * 1.6 * me
        tri = (2 / np.pi) * np.arcsin(np.sin(ph * 1.5)) * (k["TMOD"] ** 2) * 2.2 * me
        body = np.sin(ph + sq + tri)
        sub = np.sin(ph * 0.5 + 0.5 * np.pi) * np.exp(-t / (0.12 + 0.5 * dec))
        click = rng.standard_normal(n) * np.exp(-t / 0.0015) * 0.35
        y = (body + 0.55 * sub) * env(n, dec * 1.3) + click
    elif type_ in ("SD BASIC", "PC CARBON"):
        sw = k["SWEP"]
        sweep = 1 + 2.5 * sw * np.exp(-t / (0.003 + 0.03 * sw))
        ratio = (1.0 + 4.0 * k["INHM"] ** 1.5) if type_ == "SD BASIC" else (1.41 + 5.3 * k["INHM"])
        idx = (k["MDFB"] if type_ == "SD BASIC" else k["MOD"]) * 8
        me = np.exp(-t / (0.003 + 0.25 * k["MENV"]))
        y = np.zeros(n)
        pc = pm = 0.0
        prev = 0.0
        fb = (k["MDFB"] if type_ == "SD BASIC" else 0.3) * 1.2
        for i in range(n):
            f = f0 * sweep[i]
            pm += 2 * np.pi * f * ratio / FS
            m = math.sin(pm + fb * prev)
            prev = m
            pc += 2 * np.pi * f / FS
            y[i] = math.sin(pc + idx * me[i] * m)
        if type_ == "SD BASIC":
            y = 0.7 * y + 0.5 * rng.standard_normal(n) * np.exp(-t / (0.02 + 0.15 * k["DEC"])) * k["MDFB"]
        y *= env(n, dec)
    elif type_ == "SD VINTAGE":
        modes = (1.0, 1.59, 2.14, 2.30, 2.65, 2.92, 3.16, 3.50)
        sw = k["SWEP"]
        sweep = 1 + 1.0 * sw * np.exp(-t / 0.02)
        y = np.zeros(n)
        for j, r in enumerate(modes):
            rr = 1 + (r - 1) * (0.6 + 0.8 * k["INHM"])
            amp = (1.0 / (1 + j)) ** (1.5 - 1.3 * k["FCMP"])
            ph = 2 * np.pi * np.cumsum(f0 * rr * sweep) / FS
            y += amp * np.sin(ph) * env(n, dec * (1.0 - 0.08 * j))
        y /= 2.5
        wires = rng.standard_normal(n)
        b = 0.5 + 0.5 * k["MENV"]
        lp = 0.0
        out = np.zeros(n)
        for i in range(n):
            lp += 0.35 * (wires[i] - lp)
            out[i] = wires[i] - lp
        y += 0.6 * b * out * np.exp(-t / (0.03 + 0.25 * k["MENV"]))
    elif type_ == "CP VINTAGE":
        # v2 (owner, 2026-11-18: "isn't as complex or sharing the same dynamics"): four hand
        # hits at uneven gaps with their own small timing and level differences, each a
        # burst through two band-passes (the hand's crack and its slap), a diffuse tail made
        # of noise through a different band-pass with a slower decay, and velocity that moves
        # the level, the brightness and how much of the tail comes through
        sp = k["SPCR"]
        base_gap = 0.0045 + 0.010 * min(sp, 0.5) * 2
        gaps = np.cumsum([0.0] + [base_gap * g for g in (1.0, 1.18, 1.35)])
        jit = rng.uniform(-0.0006, 0.0006, 4)
        lv = (0.75, 0.9, 0.8, 1.0)
        hits = np.zeros(n)
        for j in range(4):
            at = gaps[j] + jit[j]
            d = np.clip(t - at, 0, None)
            hits += lv[j] * np.exp(-d / (0.0028 + 0.002 * j)) * (t >= at)
        last = gaps[-1]
        tail = np.exp(-np.clip(t - last, 0, None) / (0.045 + dec * 0.35)) * (t >= last)

        def bp(x, fc, r_):
            out = np.zeros(n)
            a1 = a2 = 0.0
            c = 2 * r_ * math.cos(2 * math.pi * fc / FS)
            for i in range(n):
                v = x[i] + c * a1 - r_ * r_ * a2
                a2, a1 = a1, v
                out[i] = v * (1 - r_)
            return out
        tf = 2 ** (k["TUNE"] / 12.0)
        bright = 0.6 + 0.4 * vel
        noise = rng.standard_normal(n)
        crack = bp(noise, 1250 * tf * (0.85 + 0.3 * bright), 0.94)
        slap = bp(noise, 2600 * tf * bright, 0.90)
        diffuse = bp(rng.standard_normal(n), 900 * tf, 0.88)
        clap = 7 * (crack * hits + 0.6 * slap * hits) + 5 * diffuse * tail * (0.5 + 0.5 * vel)
        if sp > 0.5:                                # crunch, faded in from 64
            c = (sp - 0.5) * 2
            clap = (1 - c) * clap + c * np.sign(clap) * np.abs(clap) ** 0.4 * 0.5
        bod = k["BODY"]
        ph = 2 * np.pi * f0 * t
        body = np.sin(ph + (1 + 4 * bod) * np.sin(ph * (1 + bod * 2))) * np.exp(-t / (0.01 + 0.3 * k["BENV"]))
        y = (1 - k["BAL"]) * clap + k["BAL"] * body
    elif type_ == "CY ALLOY":
        fa = f0 * (1 + 3 * k["RADIO"])
        fb = f0 * (1.37 + 4 * k["SHIM"])
        me = np.exp(-t / (0.01 + 0.5 * k["MENV"]))
        ph_b = 2 * np.pi * fb * t
        ph_a = 2 * np.pi * fa * t
        y = np.zeros(n)
        for j, rr in enumerate((1.0, 1.483, 1.932, 2.546, 2.630, 3.897)):
            y += np.sign(np.sin(ph_a * rr + k["MOD"] * 6 * me * np.sin(ph_b * rr)))
        hp = np.zeros(n)
        prev_x = prev_y = 0.0
        for i in range(n):
            prev_y = 0.9 * (prev_y + y[i] - prev_x)
            prev_x = y[i]
            hp[i] = prev_y
        y = hp / 6 * env(n, dec)
    y = punch(y, k["PNCH"]) * vel
    y = over(y, k["OVER"])
    pk = np.max(np.abs(y)) or 1.0
    return (y / pk * 0.8).astype(np.float64)
