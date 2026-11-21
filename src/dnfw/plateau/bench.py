"""PLATEAU's DSP program beside live.Voice: the run mode on a memory holding what the DSP would (the
frame's words: knobs, mask, the slot's track; the trig mask; the tracks' blocks in TRK_BUF; the
tables; the lines in DDR), block for block (test_plateau_program; the SHARC runner's `plateau` part)."""
from __future__ import annotations

import struct

import numpy as np

from ..fascia import bench as FB
from ..fascia import machines as FM
from ..fascia import program as FP_
from ..organ import live as OL
from ..perc.dsl import Mem, flt, bits
from ..sampler import machines as SM
from . import live as LV
from . import machines as PM
from . import program as P

BUF0 = FB.BUF0
RIDES = [PM.RIDES[c] for c in PM.CONTROLS]
TABLES = 0x8122A000
LINES = 0x82600000
F = np.float32


def panel_knobs(**kw) -> list[int]:
    d = dict(PM.KNOB_DEFAULTS, HOLD=0, TUND=0)
    d.update(kw)
    return [int(d[c]) for c in PM.CONTROLS]


def knob_value(c: str, v: int) -> int:
    """a switch's knob for its option (0 OFF, 1 ON), as the ColdFire writes it; a knob as it is"""
    return 64 * int(v) if c in LV.SWITCHES else int(v)


def knobs_words(knobs: list[int]) -> list[int]:
    return [FM.word_of(ride, min(max(knob_value(c, kv), 0), 127)) for c, kv, ride in zip(PM.CONTROLS, knobs, RIDES)]


def live_knobs(words: list[int]) -> dict:
    """the controls as the program reads them: a switch min(v * 2 >> 7, 1)"""
    out = {}
    for c, wd, ride in zip(PM.CONTROLS, words, RIDES):
        v = OL.knob_of(wd, FM.SLOTS[ride][3])
        out[c] = min(v * 2 >> 7, 1) if c in LV.SWITCHES else v
    return out


class Frame(FB.Frame):
    def plt(self, t: int, words: list[int], note: float, trig: bool, mask: int, track: int, vel: int = 127):
        for w_, ride in zip(words, RIDES):
            self.half(168 + 2 * FM.SLOTS[ride][1] + 146 * t, w_)
        for v, ride in zip(PM.mask_values(mask), PM.MASK_RIDES):
            self.half(168 + 2 * FM.SLOTS[ride][1] + 146 * t, FM.word_of(ride, v))
        self.half(148 + 2 * t, P.TYPE)
        self.half(FB.P.NOTE_OFFSET + 2 * t, FB.note_word(note))
        self.half(FB.P.VEL_OFFSET + 2 * t, (int(vel) & 0xFF) << 8)
        self.half(P.TRACK_OF + 2 * t, track)
        tw = self.w.get(FB.TRIG, 0)
        if trig:
            tw |= 1 << (16 + t)
        self.w[FB.TRIG] = tw

    def tracks(self, blocks_l, blocks_r):
        for t in range(16):
            for i in range(32):
                self.w[SM.TRK_BUF + SM.TRK_STRIDE * t + 4 * i] = bits(F(blocks_l[t][i]))
                self.w[SM.TRK_BUF + SM.TRK_STRIDE * t + 0x80 + 4 * i] = bits(F(blocks_r[t][i]))


def table_mem(L: P.Layout) -> dict[int, int]:
    data = P.tables_bytes()
    return {L.tables + 4 * k: struct.unpack_from("<I", data, 4 * k)[0] for k in range(len(data) // 4)}


class Dsp:
    def __init__(self, L: P.Layout | None = None):
        self.L = L or P.Layout(FP_.layout(), TABLES, LINES)
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


def bus_blocks(k: int, mask_src=None, seed: int = 7):
    """the sixteen tracks' blocks at block K: a few tracks playing short bursts and tones"""
    rng = np.random.default_rng(seed * 100003 + k)
    L = np.zeros((16, 32), np.float32)
    R = np.zeros((16, 32), np.float32)
    for t in (0, 2, 5, 9, 14):
        if (k // 6 + t) % 5 == 0:
            L[t] = rng.uniform(-0.4, 0.4, 32).astype(np.float32)
            R[t] = rng.uniform(-0.4, 0.4, 32).astype(np.float32)
        else:
            n = np.arange(32) + 32 * k
            L[t] = (0.2 * np.sin(2 * np.pi * (110 * (t + 1)) * n / 48000)).astype(np.float32)
            R[t] = (0.15 * np.sin(2 * np.pi * (113 * (t + 1)) * n / 48000)).astype(np.float32)
    return L, R


def compare(knobs_of, events: dict, blocks: int, slot: int = 3, mask: int = 0b0100001000100101, track: int = 3,
            dsp: Dsp | None = None, seed: int = 7, stop_at_first=True):
    """slot SLOT (playing TRACK) for BLOCKS blocks; EVENTS: block -> note (a trig); KNOBS_OF(block) -> the
    16 knobs. -> (dsp output, live output, first mismatching block or None)"""
    dsp = dsp or Dsp()
    v = LV.Voice(slot)
    a, b, first = [], [], None
    for kb in range(blocks):
        words = knobs_words(knobs_of(kb))
        trig = kb in events
        note = events.get(kb, 60.0)
        bl, br = bus_blocks(kb, seed=seed)
        f = Frame()
        f.plt(slot, words, note, trig, mask, track)
        f.tracks(bl, br)
        got = dsp.block(f, [slot])[slot]
        want = v.block(live_knobs(words), trig, FB.note_seen(note), LV.bus_sum(bl, br, mask, track))
        a.append(got)
        b.append(want)
        if first is None and not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            first = kb
            if stop_at_first:
                break
    return np.concatenate(a), np.concatenate(b), first
