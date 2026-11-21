"""THOLET (owner, 2026-11-18; the concept is Error Kit's): a grand piano with a Rhodes-ish side.

This is the float64 design model, for the owner's ear first (scripts/tholet_audition.py). The
float32 live model and the SHARC program follow it, as for every RIFT machine.

The voice, in three layers:
- **The strike**: a short transient from the Kawai grand in VCSL (CC0), one of HITS, chosen by
  HAMR. It is the first 50 ms of a real note with the pitch played back at the note's ratio, with
  a slight decay (the hammer and the string's onset, like Waldorf's transitions). FELT softens it:
  a lower level, a darker tone, and a muffled felt thud under it.
- **The strings**: a modal tail, PARTIALS partials on each of two strings detuned by STRK (the
  unison's beating).
  - Piano partials are stretched, n sqrt(1 + B n^2), with B by register. Each partial decays
    faster the higher it is (DEC sets the fundamental's T60). Amplitudes are set by where the
    hammer strikes (1/7 of the string) and by the hammer's spectrum: TONE brightens it, FELT
    darkens it a lot (the felt between hammer and string).
  - EP morphs the partials toward a Rhodes tine: a strong fundamental, a quiet octave, a bell
    partial near 5.8x that dies fast, the rest gone. The pickup's asymmetry, y + 0.35 EP y^2,
    adds the bark.
- **The cloud**: the voice's own sound, the last 0.35 s in a ring, broken into sharp grains.
  - Expodec windows (instant attack, exponential decay), 8 at most, 8..60 ms long.
  - Each grain's rate is 1 + GFM x sin(2 pi fm t) at its start: the FM decides how the note
    breaks up, from slight shimmer to metallic shards.
  - GRAN sets how much; the cloud billows out as the strings decay (its level is GRAN x
    (1 - the strings' envelope), so it swells into the tail rather than covering the strike).
  - GDEN is the grains a second, GSPR how far back in the ring they reach.

Controls 0..127. Page 1: TUNE HAMR TONE FELT / DEC EP STRK LEV. Page 2: GRAN GDEN GSIZ GFM /
GSPR REL VSNS -.
"""
from __future__ import annotations

import math
import pathlib
import wave

import numpy as np

FS = 48000
PARTIALS = 12
HIT_MS = 50
HITS = (("C2", "v4"), ("C4", "v4"), ("C4", "v2"), ("C6", "v4"), ("F#3", "v4"), ("C3", "v2"))
HIT_NAMES = ("DEEP", "BRITE", "SOFT", "HIGH", "MID", "DARK")
VCSL = pathlib.Path("/home/claude/sgossner/vcsl/Chordophones/Zithers/Grand Piano, Kawai/Sustains")
NOTE_OF = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}

DEFAULTS = dict(TUNE=64, HAMR=1, TONE=64, FELT=0, DEC=80, EP=0, STRK=40, LEV=100,
                GRAN=0, GDEN=60, GSIZ=50, GFM=30, GSPR=60, REL=40, VSNS=90)


def midi(name: str) -> int:
    n, o = name[:-1], int(name[-1])
    return 12 * (o + 1) + NOTE_OF[n]


def load_hit(k: int) -> tuple[np.ndarray, int]:
    """HITS[k]: its first HIT_MS ms from the onset, mono, at 48 kHz, with a fade; -> (samples, note)"""
    note, vel = HITS[k]
    path = VCSL / f"GPiano_sus_{note}_{vel}_rr1_Player.wav"
    with wave.open(str(path)) as w:
        sr, ch = w.getframerate(), w.getnchannels()
        raw = np.frombuffer(w.readframes(int(sr * 0.5)), np.int16).astype(float) / 32768
    x = raw.reshape(-1, ch).mean(axis=1)
    onset = int(np.argmax(np.abs(x) > 0.02 * np.abs(x).max()))
    x = x[max(onset - 24, 0):]
    t = np.arange(0, len(x) - 1, sr / FS)
    x = np.interp(t, np.arange(len(x)), x)
    n = int(FS * HIT_MS / 1000)
    x = x[:n] * np.exp(-np.arange(n) / (FS * 0.018))          # the slight decay
    x[-48:] *= np.linspace(1, 0, 48)
    return x / (np.abs(x).max() + 1e-9), midi(note)


_HITS: list | None = None


def hits():
    global _HITS
    if _HITS is None:
        _HITS = [load_hit(k) for k in range(len(HITS))]
    return _HITS


def mtof(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def render(note: float = 60, secs: float = 4.0, vel: float = 1.0, gate: float | None = None, **kn) -> np.ndarray:
    k = dict(DEFAULTS)
    k.update(kn)
    q = {c: v / 127 for c, v in k.items()}
    n = int(secs * FS)
    t = np.arange(n) / FS
    pitch = note + (k["TUNE"] - 64)
    f0 = mtof(pitch)
    felt, ep, tone = q["FELT"], q["EP"], q["TONE"]
    velg = 1 - q["VSNS"] + q["VSNS"] * vel
    rng = np.random.default_rng(int(pitch * 7) + 11)

    # -- the strike ---------------------------------------------------------------------------
    hk = min(int(k["HAMR"] * len(HITS) / 128), len(HITS) - 1)
    hit, hn = hits()[hk]
    ratio = mtof(pitch) / mtof(hn)
    idx = np.arange(0, len(hit) - 1, ratio)
    strike = np.zeros(n)
    m = min(len(idx), n)
    strike[:m] = np.interp(idx[:m], np.arange(len(hit)), hit)
    # felt: darker (a one-pole low-pass that closes with FELT), quieter, a thud under it
    cf = max(1.0 - 0.93 * felt, 0.05)                          # the low-pass's step: small = dark
    lp = np.zeros(n)
    z = 0.0
    for i in range(min(m + 64, n)):
        z += cf * (strike[i] - z)
        lp[i] = z
    strike = (1 - felt) * strike + felt * lp * 0.6
    thud = rng.standard_normal(n) * np.exp(-t / 0.012) * felt * 0.25
    tl = np.zeros(n)
    z = 0.0
    for i in range(min(n, 2400)):
        z += 0.05 * (thud[i] - z)
        tl[i] = z
    strike = (strike + tl * 4) * (0.55 + 0.45 * vel) * (0.9 - 0.4 * ep)

    # -- the strings ---------------------------------------------------------------------------
    B = 0.00015 * 2 ** ((pitch - 60) / 24)                      # stretched more up the keyboard
    t60 = (0.4 + 18 * q["DEC"] ** 2) * 2 ** (-(pitch - 48) / 30)
    detune = 2 ** (q["STRK"] * 4 / 1200)                       # up to 4 cents between the two strings
    hard = 0.12 + 0.35 * (1 - tone) + 1.4 * felt               # the hammer's spectrum falls by partial
    tine = [(1.0, 1.0, 1.0), (2.0, 0.18, 0.5), (5.8, 0.55, 0.06), (7.8, 0.08, 0.04)]
    body = np.zeros(n)
    env_ref = np.exp(-6.91 * t / t60)
    for s, dt in enumerate((1.0, detune)):
        for p in range(1, PARTIALS + 1):
            fp = p * f0 * math.sqrt(1 + B * p * p) * dt
            ap = abs(math.sin(math.pi * p / 7)) * math.exp(-hard * (p - 1)) * vel ** (0.5 + 0.1 * p)
            tp = t60 / (1 + 0.05 * p * p)
            # the Rhodes morph: partial p moves to the tine's (p <= 4), the rest fade out
            if p <= len(tine):
                tr, ta, td = tine[p - 1]
                fp = (1 - ep) * fp + ep * tr * f0 * dt
                ap = (1 - ep) * ap + ep * ta
                tp = (1 - ep) * tp + ep * t60 * td
            else:
                ap *= (1 - ep)
            if fp >= FS * 0.45:
                continue
            ph = rng.uniform(0, 2 * math.pi)
            body += ap * np.sin(2 * math.pi * fp * t + ph) * np.exp(-6.91 * t / max(tp, 0.02))
    body *= 0.35
    body = body + 0.35 * ep * body * body                       # the pickup's bark
    body *= 1 - np.exp(-t / 0.0015)                             # the string's 1.5 ms rise under the strike
    if gate is not None:                                        # the key released: the damper
        rel = 0.04 + 1.2 * q["REL"] ** 2
        after = t > gate
        body[after] *= np.exp(-6.91 * (t[after] - gate) / rel)
    y = strike * 0.8 + body

    # -- the cloud -----------------------------------------------------------------------------
    if k["GRAN"] > 0:
        ring_len = int(0.35 * FS)
        dens = 2 + 120 * q["GDEN"] ** 2                        # grains a second
        gl = int(FS * (0.008 + 0.052 * q["GSIZ"]))
        fm = 3 + 40 * q["GFM"]
        cloud = np.zeros(n)
        nxt = int(0.02 * FS)
        for g in range(4000):
            if nxt >= n - gl:
                break
            back = int(rng.uniform(0.002, 0.002 + q["GSPR"] * 0.33) * FS)
            start = max(nxt - back, 0)
            rate = 1 + q["GFM"] * 0.5 * math.sin(2 * math.pi * fm * nxt / FS) + rng.uniform(-0.02, 0.02)
            src = start + np.arange(gl) * rate
            src = src[src < nxt]
            if len(src) < 8:
                nxt += int(FS / dens)
                continue
            gw = np.exp(-np.arange(len(src)) / (len(src) * 0.22))      # expodec
            seg = np.interp(src, np.arange(n), y) * gw
            pan = 1.0
            cloud[nxt:nxt + len(seg)] += seg * pan
            nxt += max(int(rng.exponential(FS / dens)), 64)
        swell = q["GRAN"] * (1 - env_ref)
        y = y * (1 - 0.6 * q["GRAN"]) + cloud * swell * 1.2
    return y * q["LEV"] * velg
