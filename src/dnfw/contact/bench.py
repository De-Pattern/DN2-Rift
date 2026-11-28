"""CONTACT's DSP program beside live.block: the run mode on a memory holding what the DSP would (the frame's
words, the trig mask, the tables, the source blocks), block for block (test_contact_program; the SHARC
runner's `contact` part)."""
from __future__ import annotations

import struct

import numpy as np

from ..fascia import bench as FB
from ..fascia import machines as FM
from ..fascia import program as FP_
from ..organ import live as OL
from ..perc.dsl import Mem, flt, bits, f32
from ..sampler import machines as SM
from . import live as LV
from . import machines as CM
from . import program as P

BUF0 = FB.BUF0
RIDES = [CM.RIDES[c] for c in CM.CONTROLS]
TABLES = 0x8122D000
OWN = 0x82600000
F = np.float32


def panel_knobs(**kw) -> list[int]:
    d = dict(CM.KNOB_DEFAULTS, **{c: (CM.OPT_DEFAULTS[c] * 128 + 64) // len(CM.CHOICES[c]) for c in CM.OPT_DEFAULTS})
    d.update(kw)
    return [int(d[c]) for c in CM.CONTROLS]


def src_knob(o: int) -> int:
    """SRC's knob for its option O (the middle of its range)"""
    ks = [k for k in range(128) if LV.option(k, LV.NSRC) == o]
    return (ks[0] + ks[-1]) // 2


def knobs_words(knobs: list[int]) -> list[int]:
    return [FM.word_of(ride, min(max(int(k), 0), 127)) for k, ride in zip(knobs, RIDES)]


def knobs_seen(words: list[int]) -> list[int]:
    return [OL.knob_of(w, FM.SLOTS[ride][3]) for w, ride in zip(words, RIDES)]


def live_knobs(seen: list[int]) -> dict:
    return dict(zip(CM.CONTROLS, seen))


class Frame(FB.Frame):
    def cn(self, t: int, words: list[int], trig: bool, track: int | None = None, note: float = 60.0):
        for w, ride in zip(words, RIDES):
            self.half(168 + 2 * FM.SLOTS[ride][1] + 146 * t, w)
        self.half(148 + 2 * t, P.TYPE)
        self.half(FB.P.NOTE_OFFSET + 2 * t, FB.note_word(note))
        self.half(P.TRACK_OF + 2 * t, t if track is None else track)
        tw = self.w.get(FB.TRIG, 0)
        if trig:
            tw |= 1 << (16 + t)
        self.w[FB.TRIG] = tw


def table_mem(L: P.Layout) -> dict[int, int]:
    data = P.tables_bytes()
    return {L.tables + 4 * k: struct.unpack_from("<I", data, 4 * k)[0] for k in range(len(data) // 4)}


def sources(rng: np.random.Generator) -> dict[str, np.ndarray]:
    """the input's and the sixteen tracks' L and R blocks, as the DSP holds them"""
    out = {"in": rng.uniform(-1, 1, (2, 32)).astype(F)}
    for t in range(16):
        out[t] = rng.uniform(-1, 1, (2, 32)).astype(F)
    return out


def source_mem(src: dict) -> dict[int, int]:
    m = {}
    for key, lr in src.items():
        base = SM.IN_BUF if key == "in" else SM.TRK_BUF + SM.TRK_STRIDE * key
        for side in (0, 1):
            for n in range(32):
                m[base + 0x80 * side + 4 * n] = bits(f32(float(lr[side][n])))
    return m


class Dsp:
    def __init__(self, L: P.Layout | None = None):
        self.L = L or P.Layout(FP_.layout(), TABLES, OWN)
        self.base = table_mem(self.L)
        for t in range(16):
            self.base[FB.P.BUFFERS + 4 * t] = BUF0 + 128 * t
        self.mem = Mem(self._read)
        self.frame = {}
        self.steps = 0

    def _read(self, a: int) -> int:
        if a in self.frame:
            return self.frame[a]
        return self.base.get(a, 0)

    def block(self, frame: Frame, slots, src: dict) -> dict[int, np.ndarray]:
        self.frame = dict(frame.w)
        self.frame.update(source_mem(src))
        for a in list(self.frame):
            self.mem.w.pop(a, None)
        out = {}
        for t in slots:
            p, _ = P.run_voice(self.L, self._read, t, self.mem)
            self.steps = p.steps
            buf = BUF0 + 128 * t
            out[t] = np.array([flt(self.mem.get(buf + 4 * k)) for k in range(LV.BLOCK)], np.float32)
        return out
