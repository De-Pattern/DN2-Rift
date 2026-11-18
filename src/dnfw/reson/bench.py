"""RESONATOR's DSP program beside live.Voice: the run mode on a memory holding what the DSP would (the
frame's words, the trig mask, the tables), block for block (test_reson_program, the SHARC runner's
`reson` part)."""
from __future__ import annotations

import struct

import numpy as np

from ..fascia import bench as FB
from ..fascia import machines as FM
from ..organ import live as OL
from ..perc.dsl import Mem, flt
from . import live as LV
from . import machines as RM
from . import program as P

BUF0 = FB.BUF0
RIDES = [RM.RIDES[c] for c in LV.CONTROLS]


def panel_knobs(**kw) -> list[int]:
    return [int(kw.get(c, LV.DEFAULTS[c])) for c in LV.CONTROLS]


def knobs_words(knobs: list[int]) -> list[int]:
    return [FM.word_of(ride, min(max(int(k), 0), 127)) for k, ride in zip(knobs, RIDES)]


def knobs_seen(words: list[int]) -> list[int]:
    return [OL.knob_of(w, FM.SLOTS[ride][3]) for w, ride in zip(words, RIDES)]


class Frame(FB.Frame):
    def res(self, t: int, words: list[int], note: float, trig: bool, vel: int = 127):
        for w, ride in zip(words, RIDES):
            self.half(168 + 2 * FM.SLOTS[ride][1] + 146 * t, w)
        self.half(148 + 2 * t, P.TYPE)
        self.half(FB.P.NOTE_OFFSET + 2 * t, FB.note_word(note))
        self.half(FB.P.VEL_OFFSET + 2 * t, (int(vel) & 0xFF) << 8)
        tw = self.w.get(FB.TRIG, 0)
        if trig:
            tw |= 1 << (16 + t)
        self.w[FB.TRIG] = tw


def table_mem(L: P.Layout) -> dict[int, int]:
    data = P.tables_bytes()
    return {L.tables + 4 * k: struct.unpack_from("<I", data, 4 * k)[0] for k in range(len(data) // 4)}


class Dsp:
    def __init__(self, L: P.Layout | None = None, fill=None):
        self.L = L or P.layout()
        self.base = table_mem(self.L)
        for t in range(16):
            self.base[FB.P.BUFFERS + 4 * t] = BUF0 + 128 * t
        self.fill = fill
        self.mem = Mem(self._read)
        self.frame = {}
        self.steps = 0

    def _read(self, a: int) -> int:
        if a in self.frame:
            return self.frame[a]
        if a in self.base:
            return self.base[a]
        return self.fill(a) if self.fill else 0

    def block(self, frame: Frame, slots) -> dict[int, np.ndarray]:
        self.frame = frame.w
        for a in list(frame.w):
            self.mem.w.pop(a, None)
        out = {}
        for t in slots:
            p, _ = P.run_voice(self.L, self._read, t, self.mem)
            self.steps = p.steps
            buf = BUF0 + 128 * t
            out[t] = np.array([flt(self.mem.get(buf + 4 * k)) for k in range(LV.SUB)], np.float32)
        return out


def compare(knobs_of, events: dict, blocks: int, slot: int = 0, dsp: Dsp | None = None, stop_at_first=True):
    """slot SLOT for BLOCKS blocks; EVENTS: block -> note (a trig); KNOBS_OF(block) -> the 8 knobs.
    -> (dsp output, live output, first mismatching block or None)"""
    dsp = dsp or Dsp()
    v = LV.Voice(slot)
    a, b, first = [], [], None
    for k in range(blocks):
        words = knobs_words(knobs_of(k))
        trig = k in events
        note = events.get(k, 60.0)
        f = Frame()
        f.res(slot, words, note, trig)
        got = dsp.block(f, [slot])[slot]
        want = v.block(knobs_seen(words), trig, FB.note_seen(note))
        a.append(got)
        b.append(want)
        if first is None and not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            first = k
            if stop_at_first:
                break
    return np.concatenate(a), np.concatenate(b), first
