"""THOLET's DSP program beside live.Voice: the run mode on a memory holding what the DSP would (the
frame's words, the trig mask, the tables), block for block (test_tholet_program; the SHARC runner's
`tholet` part)."""
from __future__ import annotations

import struct

import numpy as np

from ..fascia import bench as FB
from ..fascia import machines as FM
from ..fascia import program as FP_
from ..organ import live as OL
from ..perc.dsl import Mem, flt
from . import live as LV
from . import machines as TM
from . import program as P

BUF0 = FB.BUF0
RIDES = [TM.RIDES[c] for c in TM.CONTROLS]
TABLES = 0x8122A000
RING = 0x82600000
F = np.float32


def panel_knobs(**kw) -> list[int]:
    d = dict(TM.KNOB_DEFAULTS, HAMR=TM.OPT_DEFAULTS["HAMR"])
    d.update(kw)
    return [int(d[c]) for c in TM.CONTROLS]


def knobs_words(knobs: list[int]) -> list[int]:
    return [FM.word_of(ride, min(max(int(k), 0), 127)) for k, ride in zip(knobs, RIDES)]


def knobs_seen(words: list[int]) -> list[int]:
    return [OL.knob_of(w, FM.SLOTS[ride][3]) for w, ride in zip(words, RIDES)]


def live_knobs(seen: list[int]) -> dict:
    """the controls by live's names; HAMR as its option (0..5), as the DSP's records give it"""
    k = dict(zip(TM.CONTROLS, seen))
    k["HAMR"] = TM.option("HAMR", k["HAMR"])
    return k


class Frame(FB.Frame):
    def dd(self, t: int, words: list[int], note: float, trig: bool, vel: int = 127, off: bool = False):
        for w, ride in zip(words, RIDES):
            self.half(168 + 2 * FM.SLOTS[ride][1] + 146 * t, w)
        self.half(148 + 2 * t, P.TYPE)
        self.half(FB.P.NOTE_OFFSET + 2 * t, FB.note_word(note))
        self.half(FB.P.VEL_OFFSET + 2 * t, (int(vel) & 0xFF) << 8)
        tw = self.w.get(FB.TRIG, 0)
        if trig:
            tw |= 1 << (16 + t)
        self.w[FB.TRIG] = tw
        ow = self.w.get(P.OFF_WORD, 0)
        if off:
            ow |= 1 << t
        self.w[P.OFF_WORD] = ow


def table_mem(L: P.Layout) -> dict[int, int]:
    data = P.tables_bytes()
    return {L.tables + 4 * k: struct.unpack_from("<I", data, 4 * k)[0] for k in range(len(data) // 4)}


class Dsp:
    def __init__(self, L: P.Layout | None = None):
        self.L = L or P.Layout(FP_.layout(), TABLES, RING)
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


def compare(knobs_of, events: dict, blocks: int, slot: int = 0, dsp: Dsp | None = None, vel: int = 127,
            stop_at_first=True, offs=()):
    """slot SLOT for BLOCKS blocks; EVENTS: block -> note (a trig); KNOBS_OF(block) -> the 16 knobs.
    -> (dsp output, live output, first mismatching block or None)"""
    dsp = dsp or Dsp()
    v = LV.Voice(slot)
    a, b, first = [], [], None
    for k in range(blocks):
        words = knobs_words(knobs_of(k))
        trig = k in events
        note = events.get(k, 60.0)
        f = Frame()
        off = k in offs
        f.dd(slot, words, note, trig, vel, off)
        got = dsp.block(f, [slot])[slot]
        want = v.block(live_knobs(knobs_seen(words)), trig, FB.note_seen(note), vel, off)
        a.append(got)
        b.append(want)
        if first is None and not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            first = k
            if stop_at_first:
                break
    return np.concatenate(a), np.concatenate(b), first
