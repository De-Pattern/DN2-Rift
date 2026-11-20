"""LIGATURE's DSP program beside live.SlotVoice: the run mode (dnfw.silt.program) on a memory holding what the
DSP would (the frame's words, the trig and note-off masks, the tables), block for block
(test_ligature_program, the SHARC runner's `ligature` part)."""
from __future__ import annotations

import struct

import numpy as np

from ..fascia import bench as FB
from ..fascia import machines as FM
from ..organ import live as OL
from ..perc.dsl import Mem, flt
from . import live as LV
from . import program as P

BUF0 = FB.BUF0


def panel_knobs(**kw) -> list[int]:
    """a panel (PATCH by name or number) as the 32 knobs a player sets"""
    out = []
    for c in LV.CONTROLS:
        v = kw.get(c, LV.DEFAULTS[c])
        if c == "PATCH":
            if isinstance(v, str):
                v = [n for n, *_r in LV.PATCHES].index(v)
            v = (2 * int(v) + 1) * 128 // (2 * LV.NP)
        out.append(int(v))
    return out


def knobs_words(knobs: list[int]) -> list[int]:
    return [FM.word_of(ride, min(max(int(k), 0), 127)) for k, ride in zip(knobs, OL.RIDES)]


def knobs_seen(words: list[int]) -> list[int]:
    return [OL.knob_of(w, FM.SLOTS[ride][3]) for w, ride in zip(words, OL.RIDES)]


class Frame(FB.Frame):
    def lig(self, t: int, words: list[int], note: float, trig: bool, vel: int = 127, off: bool = False):
        for w, ride in zip(words, OL.RIDES):
            self.half(168 + 2 * FM.SLOTS[ride][1] + 146 * t, w)
        self.half(148 + 2 * t, P.TYPE)
        self.half(P.NOTE_OFFSET + 2 * t, FB.note_word(note))
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
    def __init__(self, L: P.Layout | None = None, fill=None):
        self.L = L or P.layout()
        self.base = table_mem(self.L)
        for t in range(16):
            self.base[FB.P.BUFFERS + 4 * t] = BUF0 + 128 * t
        self.fill = fill
        self.mem = Mem(self._read)
        self.frame = {}
        self.steps = 0

    def set_table(self, words) -> None:
        """v0.12: the WIRE area's words (None: none sent, its magic word zero)"""
        for k in range(LV.WTABLE_WORDS):
            self.base[self.L.wire + 4 * k] = 0 if words is None else int(words[k]) & 0xFFFFFFFF
            self.mem.w.pop(self.L.wire + 4 * k, None)

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


def compare(knobs_of, events: dict, blocks: int, slot: int = 0, dsp: Dsp | None = None,
            offs=(), vels: dict | None = None, stop_at_first=True, table_of=None):
    """slot SLOT for BLOCKS blocks; EVENTS: block -> note (a trig); OFFS: the blocks with a note-off;
    KNOBS_OF(block) -> the 32 knobs. -> (dsp output, live output, first mismatching block or None)"""
    dsp = dsp or Dsp()
    v = LV.SlotVoice(slot)
    a, b, first = [], [], None
    for k in range(blocks):
        if table_of is not None:              # v0.12: the WIRE table as the block finds it
            tb = table_of(k)
            dsp.set_table(tb)
            v.table = None if tb is None else list(tb)
        words = knobs_words(knobs_of(k))
        trig = k in events
        note = events.get(k, 60.0)
        vel = (vels or {}).get(k, 127)
        off = k in offs
        f = Frame()
        f.lig(slot, words, note, trig, vel, off)
        got = dsp.block(f, [slot])[slot]
        want = v.dsp_block(knobs_seen(words), trig, FB.note_seen(note), vel, off)
        a.append(got)
        b.append(want)
        if first is None and not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            first = k
            if stop_at_first:
                break
    return np.concatenate(a), np.concatenate(b), first
