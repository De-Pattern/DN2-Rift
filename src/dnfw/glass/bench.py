"""GLASS's DSP program beside live.Voice: the run mode on a memory holding what the DSP would at the end of
FASCIA's walk (the slot's buffer, its record's filter floats, the frame's filter type, note and trig, the
state in DDR), block for block (test_glass_program; the SHARC runner's `glass` part)."""
from __future__ import annotations

import numpy as np

from ..fascia import bench as FB
from ..fascia import program as FP_
from ..perc.dsl import Mem, flt, bits
from ..waverider import voice as WV
from . import live as LV
from . import program as P

BUF0 = FB.BUF0
STATE = 0x82680000
F = np.float32


def rec_floats(**kw) -> dict:
    d = {LV.R_TYPE: 0.0, LV.R_FREQ: 0.6, LV.R_RES: 0.8, LV.R_LPG: 0.0, LV.R_ATK: 0.1, LV.R_DEC: 0.5,
         LV.R_ABND: 0.5, LV.R_DBND: 0.5, LV.R_DEPTH: 0.5, LV.R_KEYT: 0.0}
    names = {"TYPE": LV.R_TYPE, "FREQ": LV.R_FREQ, "RES": LV.R_RES, "LPG": LV.R_LPG, "ATK": LV.R_ATK,
             "DEC": LV.R_DEC, "ABND": LV.R_ABND, "DBND": LV.R_DBND, "DEPTH": LV.R_DEPTH, "KEYT": LV.R_KEYT}
    for kk, v in kw.items():
        d[names[kk]] = v
    return {a: F(v) for a, v in d.items()}


class Frame(FB.Frame):
    def glass(self, t: int, rec: dict, note: float, trig: bool, x: np.ndarray, ftype: int = LV.FILTER_TYPE):
        self.half(P.FILTER_HDR + 2 * t, ftype)
        self.half(FB.P.NOTE_OFFSET + 2 * t, FB.note_word(note))
        base = WV.TRACKS + P.REC_STRIDE * t
        for off, v in rec.items():
            self.w[base + off] = bits(F(v))
        for i in range(32):
            self.w[BUF0 + 128 * t + 4 * i] = bits(F(x[i]))
        tw = self.w.get(FB.TRIG, 0)
        if trig:
            tw |= 1 << (16 + t)
        self.w[FB.TRIG] = tw


class Dsp:
    def __init__(self, L: P.Layout | None = None):
        self.L = L or P.Layout(FP_.layout(), STATE)
        self.base = {FB.P.BUFFERS + 4 * t: BUF0 + 128 * t for t in range(16)}
        self.mem = Mem(self._read)
        self.frame = {}

    def _read(self, a: int) -> int:
        if a in self.frame:
            return self.frame[a]
        return self.base.get(a, 0)

    def block(self, frame: Frame, slots=None) -> dict[int, np.ndarray]:
        self.frame = frame.w
        for a in list(frame.w):
            self.mem.w.pop(a, None)
        p, _ = P.run_walk(self.L, self._read, self.mem)
        return {t: np.array([flt(self.mem.get(BUF0 + 128 * t + 4 * k)) for k in range(32)], np.float32)
                for t in (slots or range(16))}


def source(kb: int, seed: int = 3) -> np.ndarray:
    """a slot's dry block: a click every 40 blocks over a little noise and a saw"""
    rng = np.random.default_rng(seed * 7919 + kb)
    n = np.arange(32) + 32 * kb
    x = (0.3 * ((n * 220.0 / 48000.0) % 1.0 - 0.5) + 0.02 * rng.standard_normal(32)).astype(np.float32)
    if kb % 40 == 1:
        x[0] += F(1.0)
    return x


def compare(rec_of, events: dict, blocks: int, slot: int = 2, dsp: Dsp | None = None, src=source):
    """slot SLOT on GLASS for BLOCKS blocks; EVENTS: block -> note (a trig); REC_OF(b) -> the record's
    floats. -> (dsp out, live out, first mismatch or None)"""
    dsp = dsp or Dsp()
    v = LV.Voice()
    a, b, first = [], [], None
    for kb in range(blocks):
        rec = rec_of(kb)
        trig = kb in events
        note = events.get(kb, 60.0)
        x = src(kb)
        f = Frame()
        f.glass(slot, rec, note, trig, x)
        got = dsp.block(f, [slot])[slot]
        want = v.block(rec, trig, FB.note_seen(note), x)
        a.append(got)
        b.append(want)
        if first is None and not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            first = kb
            break
    return np.concatenate(a), np.concatenate(b), first
