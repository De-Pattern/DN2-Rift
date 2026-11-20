"""SMEAR's stage (smear.asm: the mailboxes, the lanes, the clock, the power-on tables) in run
mode equals stage.Model (live.Voice under the stage's rules) bit for bit."""
import numpy as np

from dnfw.perc.dsl import Mem, Prog
from dnfw.smear import live as LV
from dnfw.smear import stage as ST

SCR, MBOX, STATE, VB, TAB, VTAB, QS = 0x0100_0000, 0x0110_0000, 0x4000_0000, 0x0300_0000, 0x2000_0000, 0x2100_0000, 0x2200_0000
LANES = ((0x0500_0000, 0x6000_0000), (0x0510_0000, 0x6100_0000))
BUFS, OUT0 = 0x0700_0000, 0x0800_0000
POOLA, POOLB = 0x1000_0000, 0x1100_0000


def layout():
    return ST.SLayout(SCR, MBOX, STATE, VB, TAB, VTAB, QS, LANES, BUFS)


def test_the_stage_is_the_contract():
    sr = 48000
    i = np.arange(16000)
    bufa = (0.4 * np.sin(2 * np.pi * 220 * i / sr)).astype(np.float32)
    bufb = (0.3 * np.sin(2 * np.pi * 330 * i / sr) * np.exp(-(i % 4000) / 1500)).astype(np.float32)
    mem = Mem()
    for k, x in enumerate(bufa):
        mem.put(POOLA + 4 * k, ST.u32(x))
    for k, x in enumerate(bufb):
        mem.put(POOLB + 4 * k, ST.u32(x))
    S = layout()
    ST.load_tables(mem, S)
    for t in range(16):
        mem.put(BUFS + 4 * t, OUT0 + 128 * t)
    model = ST.Model()
    peaks = {}
    ST.stage(Prog("run", mem=mem), S)        # the power-on block: the tables, silence
    rate = 44100 / 48000
    # tracks 0, 3 and 5 SMEAR; 5 plays an empty slot; notes take and steal the two lanes
    trigs = {(0, 0), (3, 2), (5, 4), (0, 30), (3, 31), (5, 40), (3, 60)}
    kn = {0: dict(LV.DEFAULTS, BLND=0, SPD=72), 3: dict(LV.DEFAULTS, BLND=64, SPD=90),
          5: dict(LV.DEFAULTS, BLND=127, DENS=100)}
    gone = {3: range(70, 80)}                   # track 3 leaves for 10 blocks: its lane is freed
    for n in range(90):
        mail = {}
        for t, k in kn.items():
            if t in gone and n in gone[t]:
                continue
            buf = bufa if t == 0 else (bufb if t == 3 else np.zeros(0, np.float32))
            tr = float(np.float32(2 ** ((t - 2) / 12) * rate))
            trig = (t, n) in trigs
            mail[t] = (buf, rate, tr, trig, k)
            base = POOLA if t == 0 else POOLB
            mem.put(S.mb(t, ST.MB_ON), 1)
            mem.put(S.mb(t, ST.MB_TRIG), int(trig))
            mem.put(S.mb(t, ST.MB_TR), ST.u32(tr))
            mem.put(S.mb(t, ST.MB_RATE), ST.u32(np.float32(rate)))
            mem.put(S.mb(t, ST.MB_BASE), base)
            mem.put(S.mb(t, ST.MB_FRAMES), len(buf))
            mem.put(S.mb(t, ST.MB_FMT), 0)
            for c, name in enumerate(LV.CONTROLS):
                mem.put(S.mb(t, ST.MB_KN + c), k[name])
        want = model.block(mail)
        p = Prog("run", mem=mem)
        ST.stage(p, S)
        for t, y in want.items():
            got = np.array([mem.get(OUT0 + 128 * t + 4 * s) for s in range(32)], np.uint32).view(np.float32)
            assert got.tobytes() == np.asarray(y, np.float32).tobytes(), (n, t, got[:3], y[:3])
            assert mem.get(S.mb(t, ST.MB_ON)) == 0
            peaks[t] = max(peaks.get(t, 0.0), float(np.abs(got).max()))
        assert [mem.get(S.LOWN0), mem.get(S.LOWN1)] == model.own, (n, model.own)
    assert model.own[0] or model.own[1]
    assert peaks[0] > 0.01 and peaks[3] > 0.01 and peaks[5] == 0.0, peaks


def test_emits():
    p = Prog("emit", prefix="smr")
    text = ST.program(layout(), 0xBE0000)
    n = sum(1 for ln in text.splitlines() if ln.startswith("      ") and not ln.strip().startswith("//"))
    print("instructions", n)
    assert "JUMP 0xbe0000;" in text
