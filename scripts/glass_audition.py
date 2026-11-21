"""GLASS's reference model for listening (src/dnfw/fx/glass.py).

    PYTHONPATH=src python3 scripts/glass_audition.py OUTDIR

48 kHz mono WAVs; each file says what it is in OUTDIR/LISTEN.md. Where a plain SVF is heard first,
it is the comparison (a Chamberlin SVF, clipped: the kind of filter that whines and crackles there).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

from dnfw.fx import glass as G
from dnfw.fx.common import write_wav

SR = int(G.RATE)
spec = importlib.util.spec_from_file_location("fa", Path(__file__).with_name("fx_audition.py"))
FA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FA)
GAP = np.zeros(SR // 3)


def clicks(times, amp=0.9, width=8):
    x = np.zeros(int((max(times) + 2.5) * SR))
    for t in times:
        i = int(t * SR)
        x[i:i + width] = amp
        x[i + width:i + 2 * width] = -amp * 0.6
    return x


def svf_run(x, cutoff, res):
    f = G.SVF(cutoff, res)
    return np.array([f.tick(v) for v in x])


def main(out: str) -> None:
    o = Path(out)
    o.mkdir(parents=True, exist_ok=True)
    notes = ["# GLASS auditions (the reference model, not the DN2 yet)\n"]

    def save(name, x, what):
        x = np.asarray(x, float)
        x = x / max(np.max(np.abs(x)), 1e-9) * 0.9          # each file at the same peak
        write_wav(o / f"glass_{name}.wav", np.concatenate([x, GAP]))
        notes.append(f"- `glass_{name}.wav`: {what}\n")
        print(name, flush=True)

    # 1. pings: hard clicks at rising cutoffs, RES high (the glass)
    hits = clicks([0.0, 0.6, 1.2, 1.8])
    parts = [G.run(hits, c, 0.9) for c in (330.0, 660.0, 1320.0, 2640.0)]
    save("01_pings", np.concatenate(parts), "hard clicks into GLASS, RES 0.9 (about a 1.5 s ring), cutoff 330 / 660 / 1320 / 2640 Hz: the tapped glass")
    # 2. the same through a plain SVF, clipped (the comparison), then GLASS
    hits2 = clicks([0.0, 0.5, 1.0], amp=1.0)
    save("02_vs_plain_svf", np.concatenate([svf_run(hits2, 880.0, 0.98), GAP, G.run(hits2, 880.0, 0.9)]),
         "a plain SVF at high resonance (hard hits: it clips and crackles), then GLASS on the same hits")
    # 3. a drum loop, cutoff swept, RES high: the low end kept
    d, _ = FA._drums(2)
    sweep = 200.0 * 2.0 ** (5.0 * np.linspace(0, 1, len(d)))
    save("03_drums_sweep", np.concatenate([d, GAP, G.run(d, sweep, 0.85), GAP, G.run(d, sweep, 0.85, keep_low=False)]),
         "a drum loop dry, then GLASS swept 200 Hz to 6.4 kHz at RES 0.85 (the kick kept), then the same without the low-end keep")
    # 4. the envelope's bends on a pinged note: ATK/DEC BEND -1, 0, +1
    n = int(1.2 * SR)
    seq = []
    for ab, db in ((-1.0, -1.0), (0.0, 0.0), (1.0, 1.0)):
        env = G.envelope(n, 0.15, 0.6, 0.0, 0.2, n, ab, db)
        src = np.random.default_rng(1).standard_normal(n) * 0.15
        seq += [G.run(src, 200.0, 0.8, env=env, depth=5.0), GAP]
    save("04_bends", np.concatenate(seq), "noise through GLASS, the envelope 5 octaves: BENDs exponential, linear, logarithmic")
    # 5. LPG: bongo-like hits
    t = [0.0, 0.25, 0.5, 0.875, 1.0, 1.5, 1.625, 1.75]
    x = clicks(t, amp=0.8)
    lp = G.vactrol(len(x), [int(v * SR) for v in t], fall=0.18)
    save("05_lpg", G.run(x, 1600.0, 0.75, lpg=lp), "LPG: clicks, the filter and level closed together by the vactrol contour")
    # 6. modes on the plucks: LP, BP, HP
    pl, _ = FA._plucks()
    save("06_modes", np.concatenate([G.run(pl, 1200.0, 0.8, mode=m) for m in (0.0, 0.5, 1.0)]),
         "plucks through GLASS at RES 0.8: LP, then BP, then HP")
    # 7. the synth line, RES 1 (self-ringing), cutoff on the note
    ln, _ = FA._line()
    save("07_line_res_max", G.run(ln, 700.0, 1.0), "the synth line at RES 1: the filter rings at its cutoff, rounded, never clipped")
    (o / "LISTEN.md").write_text("".join(notes))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/glass")
