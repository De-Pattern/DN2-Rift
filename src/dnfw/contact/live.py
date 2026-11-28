"""CONTACT's reference model (RIFT, the FX machine's phase 0: THRU). float32 after every operation and
ORGAN's exp2f, so the SHARC program (dnfw.contact.program) is held to it bit for bit.

**The source.** SRC: IN (the input's L and R averaged), IN L, IN R, or T1..T16 (that track's block as
Overbridge and the recorder read it, SM.TRK_BUF: after its own filter, amp and pan, the block before;
L and R averaged). The FX track's own track is never its source (x 0: silence, signed zeros). Each block: 32 samples
x = L cl + R cr (cl, cr: 0.5 and 0.5, 1 and 0, 0 and 1).

**The level.** GAIN 0 is off; 1..127 = (GAIN - 96) x 12/31 dB (96 0 dB, 127 +12 dB), as
exp2f((GAIN - 96) x GK). LEV x 1.27 / 127 after it (100 about unity). out = x (g lev).

**The voice.** One a track: a note claims its track; any other CONTACT voice of that track goes
silent and ends (one effect per FX track, however many notes are held). The voice sounds from its
note until the track's amp lets it go (the walk's life words).
"""
from __future__ import annotations

import numpy as np

from ..organ.live import F, exp2f

BLOCK = 32
PAGE1 = ("SRC", "GAIN", "SENS", "EXC", "CLST", "TONE", "MIX", "LEV")
PAGE2 = ("BODY", "TUNE", "DCAY", "DAMP", "SPRD", "SIZE", "BRIT", "WATR")
CONTROLS = PAGE1 + PAGE2
NSRC = 19
INV127 = F(F(1.0) / F(127.0))
GK = F(F(12.0) / F(31.0) / F(6.0205999))       # dB to octaves of amplitude: (GAIN - 96) x GK
LEVK = F(1.27)
HALF = F(0.5)


def option(k: int, n: int) -> int:
    return min((min(max(int(k), 0), 127) * n) >> 7, n - 1)


def coefficients(src: int) -> tuple:
    """(cl, cr) for SRC's option"""
    if src == 1:
        return F(1.0), F(0.0)
    if src == 2:
        return F(0.0), F(1.0)
    return HALF, HALF


def level(k: dict):
    """g x lev, as the program computes it"""
    lev = F(F(F(k["LEV"]) * INV127) * LEVK)
    if int(k["GAIN"]) <= 0:
        g = F(0.0)
    else:
        g = exp2f(F(F(F(k["GAIN"]) - F(96.0)) * GK))
    return F(g * lev)


def block(k: dict, left, right, own_track: int):
    """one block: K the sixteen knobs (0..127), LEFT / RIGHT the source's 32 samples each (the input or
    a track; whatever SRC names), OWN_TRACK the FX track's own. -> 32 float32"""
    src = option(k["SRC"], NSRC)
    cl, cr = coefficients(src)
    gl = F(0.0) if src >= 3 and src - 3 == own_track else level(k)   # its own track: x 0 (signed zeros, as the DSP)
    out = np.empty(BLOCK, F)
    for n in range(BLOCK):
        x = F(F(F(left[n]) * cl) + F(F(right[n]) * cr))
        out[n] = F(x * gl)
    return out
