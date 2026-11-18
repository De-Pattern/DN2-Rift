"""SMEAR's grains: the DSL program (program.emit_grn) in run mode equals live.Grn bit for bit,
block after block, through launches, steals, wraps and the limiter."""
import struct

import numpy as np

from dnfw.perc.dsl import Mem, Prog
from dnfw.smear import live as LV
from dnfw.smear import model as M
from dnfw.smear import program as P

BUFA, WINA, GA = 0x1000_0000, 0x2000_0000, 0x3000_0000


def u32(x):
    return struct.unpack("<I", struct.pack("<f", float(x)))[0]


def _packed(mem, a, buf):
    q = np.round(buf * 32767).astype(np.int16)
    if len(q) % 2:
        q = np.concatenate([q, [0]]).astype(np.int16)
    for k, w in enumerate(q.view(np.uint32)):
        mem.put(a + 4 * k, int(w))
    return q[:len(buf)].astype(np.float32) / np.float32(32768)


def test_grains_are_the_contract(fmt=0):
    sr = 48000
    i = np.arange(5000)
    buf = (0.5 * np.sin(2 * np.pi * 440 * i / sr) + 0.2 * np.sin(2 * np.pi * 61 * i / sr)).astype(np.float32)
    win = M.WINDOWS["GAUS"].astype(np.float32)
    G = P.GLayout(GA)
    mem = Mem()
    if fmt:
        buf = _packed(mem, BUFA, buf)
    else:
        for k, x in enumerate(buf):
            mem.put(BUFA + 4 * k, u32(x))
    mem.put(G.FMT, fmt)
    g = LV.Grn(buf, win)
    for k, x in enumerate(win):
        mem.put(WINA + 4 * k, u32(x))
    mem.put(G.SIZE, len(buf))
    mem.put(G.BASE, BUFA)
    mem.put(G.WINP, WINA)
    mem.put(G.RNG, 0x1234567)
    mem.put(G.GAIN, u32(1.0))
    rng = np.random.default_rng(5)
    steps = []
    for blk in range(60):
        read = int(rng.integers(0, len(buf)))
        pitch = float(rng.choice([0.5, 1.0, 1.37, 3.9]))
        ginc = float(rng.choice([0.0, 0.002, 0.03, 0.2]))
        envinc = float(rng.choice([0.0, 1 / 300, 1 / 40, 0.2]))
        spray, prand = float(rng.random()), float(rng.random())
        y = g.block(read, pitch, ginc, envinc, spray, prand)
        for name, val in (("READ", read), ("PITCH", u32(pitch)), ("GINC", u32(np.float32(ginc))),
                          ("ENVINC", u32(np.float32(envinc))), ("SPRAY", u32(np.float32(spray))),
                          ("PRAND", u32(np.float32(prand)))):
            mem.put(getattr(G, name), val)
        p = Prog("run", mem=mem)
        P.emit_grn(p, G)
        steps.append(p.steps)
        out = np.array([mem.get(G.OUT + 4 * k) for k in range(32)], np.uint32).view(np.float32)
        assert out.tobytes() == y.tobytes(), blk
    print("steps a block, most", max(steps))
    assert max(steps) < 25_000          # 8 grains, int16: about 23k


def test_emits():
    p = Prog("emit", prefix="smg")
    P.emit_grn(p, P.GLayout(GA))
    assert "JUMP" in p.text()


def test_grains_int16():
    test_grains_are_the_contract(fmt=1)
