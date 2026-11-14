"""What the effect models share: the rate, a jit that falls back to plain Python, the
xorshift generator Viscera uses, mu-law, and a WAV writer."""
from __future__ import annotations

import wave
from pathlib import Path

import numpy as np

RATE = 48000.0

try:                                    # the models are reference code: numba only for speed
    from numba import njit
except ImportError:                     # pragma: no cover
    def njit(*a, **k):
        if a and callable(a[0]):
            return a[0]
        return lambda f: f


@njit(cache=True)
def xorshift(s):
    """One step of Viscera's generator (vsc_engine.c rnd()): -> (new state, value)."""
    s ^= (s << 13) & 0xFFFFFFFF
    s ^= s >> 17
    s ^= (s << 5) & 0xFFFFFFFF
    return s, s


@njit(cache=True)
def uni(s):
    """-> (state, a uniform in [0, 1)), as rndu()."""
    s, v = xorshift(s)
    return s, (v >> 8) * (1.0 / 16777216.0)


@njit(cache=True)
def ulaw_enc(x):
    x = min(max(x, -1.0), 1.0)
    s = int(x * 32767.0)
    sign = 0
    if s < 0:
        s = -s
        sign = 0x80
    if s > 32635:
        s = 32635
    s += 0x84
    e = 7
    while e > 0 and not (s >> (e + 7)) & 1:
        e -= 1
    mant = (s >> (e + 3)) & 15
    return (~(sign | (e << 4) | mant)) & 0xFF


def ulaw_table() -> np.ndarray:
    t = np.zeros(256)
    for c in range(256):
        u = (~c) & 0xFF
        sign, e, mant = u & 0x80, (u >> 4) & 7, u & 15
        s = (((mant << 3) + 0x84) << e) - 0x84
        t[c] = (-s if sign else s) / 32768.0
    return t


ULAW = ulaw_table()


def write_wav(path: Path | str, x: np.ndarray, *, peak: float = 0.98) -> None:
    """Mono or (n, 2) stereo, normalised only if it would clip."""
    x = np.asarray(x, dtype=float)
    pk = float(np.max(np.abs(x))) or 1.0
    x = x / max(pk, 1.0) * peak if pk > peak else x
    ch = 1 if x.ndim == 1 else x.shape[1]
    with wave.open(str(path), "wb") as w:
        w.setnchannels(ch)
        w.setsampwidth(2)
        w.setframerate(int(RATE))
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
