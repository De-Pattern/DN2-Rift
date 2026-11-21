"""SMEAR's whole voice (program.emit_voice) in run mode equals live.Voice bit for bit, block
after block: notes, both lanes, every BLND region, speeds either way, knob moves."""
import struct

import numpy as np

from dnfw.perc.dsl import Mem, Prog
from dnfw.smear import live as LV
from dnfw.smear import program as P

BUFA, TAB, VTAB, VB, VST = 0x1000_0000, 0x2000_0000, 0x2100_0000, 0x0300_0000, 0x4000_0000
LANES = ((0x0500_0000, 0x6000_0000), (0x0510_0000, 0x6100_0000))


def u32(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def test_voice_is_the_contract():
    sr = 48000
    i = np.arange(20000)
    buf = (0.4 * np.sin(2 * np.pi * 220 * i / sr) + 0.2 * np.sin(2 * np.pi * 1310 * i / sr)
           * np.exp(-((i % 6000) / 2000.0))).astype(np.float32)
    mem = Mem()
    for k, x in enumerate(buf):
        mem.put(BUFA + 4 * k, u32(x))
    for k, w in enumerate(P.tables_words()):
        mem.put(TAB + 4 * k, w)
    for k, w in enumerate(P.voice_tables_words()):
        mem.put(VTAB + 4 * k, w)
    V = P.VLayout(VB, TAB, VTAB, LANES)
    rate = 44100 / 48000
    voice = LV.Voice(buf, rate)
    script = {0: dict(BLND=0, SPD=72), 40: dict(BLND=20), 70: dict(BLND=64, SPD=40),
              90: dict(BLND=100, DENS=100, OVLP=110, SPRY=50, PRND=60, WIN=40),
              110: dict(BLND=127, SPD=88, STRT=60, SIZE=70), 125: dict(BLND=10, SPD=20)}
    trigs = {0: 0, 100: 1, 125: 0}
    k = dict(LV.DEFAULTS)
    lane = None
    tr = float(np.float32(2 ** (3 / 12) * rate))
    for n in range(150):
        k.update(script.get(n, {}))
        trig = n in trigs
        if trig:
            lane = trigs[n]
        y = voice.block(k, tr, trig, n, lane)
        for c, name in enumerate(LV.CONTROLS):
            mem.put(V.KN0 + 4 * c, k[name])
        for w, val in (("TR", u32(tr)), ("RATE", u32(np.float32(rate))), ("TRIG", int(trig)),
                       ("SIZE", len(buf)), ("BASE", BUFA), ("FMT", 0), ("CLOCK", n),
                       ("LANE", -1 if lane is None else lane), ("VSTATE", VST)):
            mem.put(getattr(V, w), val)
        p = Prog("run", mem=mem)
        P.emit_voice(p, V)
        out = np.array([mem.get(V.OUT + 4 * s) for s in range(32)], np.uint32).view(np.float32)
        assert out.tobytes() == y.tobytes(), (n, out[:4], y[:4])
    assert np.max(np.abs(y)) > 0


def test_emits():
    p = Prog("emit", prefix="smx")
    P.emit_voice(p, P.VLayout(VB, TAB, VTAB, LANES))
    print("instructions", sum(1 for l in p.lines if l.startswith("      ") and "//" not in l[:8]))
