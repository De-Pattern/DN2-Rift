"""ORGAN's DSP program beside live.Voice: the run mode (dnfw.organ.program) on a memory holding what
the DSP would (the frame's words, the trig, the tables), block for block (test_organ_program, the
SHARC runner's `organ` part)."""
from __future__ import annotations

import struct

import numpy as np

from ..fascia import bench as FB
from ..fascia import machines as FM
from ..perc.dsl import Mem, flt
from . import live as LV
from . import program as P

BUF0 = FB.BUF0
DEFAULTS = {"STOP": 1, "R8": 110, "R4": 70, "R2": 40, "CHIFF": 40, "SPEECH": 50, "SPREAD": 40,
            "AIR": 25, "WIND": 30, "TRATE": 60}      # Ravel's (docs/organ.md); STOP an option 0..4


def knobs_words(panel: dict) -> list[int]:
    """the panel (STOP an option, the rest 0..127) as the record words of the 16 rides"""
    out = []
    for j, (c, ride) in enumerate(zip(LV.CONTROLS, LV.RIDES)):
        v = int(panel.get(c, DEFAULTS.get(c, 0)))
        if j == 0:                                    # an option: its knob span's middle (a detent)
            out.append(FM.rep_word(ride, min(max(v, 0), 4)) if ride in FM.CHOICES and len(FM.CHOICES[ride]) == 5
                       else _stop_word(v))
        else:
            out.append(FM.word_of(ride, min(max(v, 0), 127)))
    return out


def _stop_word(o: int) -> int:
    top = FM.SLOTS["TYPA"][3]
    ks = [k for k in range(128) if min((k * 5) >> 7, 4) == o]
    want = (ks[0] + ks[-1]) // 2
    v = min(range(top + 1), key=lambda v: (abs(LV.knob_of(v << 8, top) - want), v))
    return v << 8


def knobs_seen(words: list[int]) -> list[int]:
    return [LV.knob_of(w, FM.SLOTS[ride][3]) for w, ride in zip(words, LV.RIDES)]


class Frame(FB.Frame):
    def organ(self, t: int, words: list[int], note: float, trig: bool, vel: int = 127):
        for w, ride in zip(words, LV.RIDES):
            self.half(168 + 2 * FM.SLOTS[ride][1] + 146 * t, w)
        self.half(148 + 2 * t, P.TYPE)
        self.half(P.NOTE_OFFSET + 2 * t, FB.note_word(note))
        self.half(FB.P.VEL_OFFSET + 2 * t, (int(vel) & 0xFF) << 8)     # v0.5: the trig's velocity
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


def compare(panel_of, events: dict, blocks: int, slot: int = 0, dsp: Dsp | None = None, vels: dict | None = None):
    """slot SLOT for BLOCKS blocks; EVENTS: block -> note (a trig); PANEL_OF(block) -> panel.
    -> (dsp output, live output, first mismatching block or None)"""
    dsp = dsp or Dsp()
    v = LV.Voice(LV.tables(), slot)
    a, b, first = [], [], None
    for k in range(blocks):
        words = knobs_words(panel_of(k))
        trig = k in events
        note = events.get(k, 60.0)
        vel = (vels or {}).get(k, 127)
        f = Frame()
        f.organ(slot, words, note, trig, vel)
        got = dsp.block(f, [slot])[slot]
        want = v.block(knobs_seen(words), trig, FB.note_seen(note), vel)
        a.append(got)
        b.append(want)
        if first is None and not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            first = k
    return np.concatenate(a), np.concatenate(b), first
