"""PLATEAU's reference model, for listening (src/dnfw/fx/plateau.py).

    PYTHONPATH=src python3 scripts/plateau_audition.py OUTDIR

One stereo 48 kHz 16-bit WAV a setting, each the same sources (a drum loop, a synth line,
plucks) dry then through PLATEAU, plus a HOLD (freeze) and a TUNED demo. OUTDIR/LISTEN.md lists them.
"""
from __future__ import annotations

import importlib.util
import sys
import wave
from pathlib import Path

import numpy as np

from dnfw.fx.plateau import Plateau, RATE

SR = int(RATE)
spec = importlib.util.spec_from_file_location("fa", Path(__file__).with_name("fx_audition.py"))
FA = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FA)


def wav2(path: Path, L: np.ndarray, R: np.ndarray) -> None:
    pk = max(np.max(np.abs(L)), np.max(np.abs(R)), 1e-9)
    s = np.clip(np.stack([L, R], 1) / pk * 0.95, -1, 1)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((s * 32767).astype("<i2").tobytes())


def source() -> np.ndarray:
    d, _ = FA._drums(1)
    l, _ = FA._line()
    p, _ = FA._plucks()
    gap = np.zeros(int(0.2 * SR))
    return np.concatenate([d, gap, l, gap, p])


SETTINGS = [
    ("01_plate_medium", "A medium plate: SIZE 0.6, DECAY 0.6, DAMP 0.3, light modulation", {}),
    ("02_small_bright", "Small and bright: SIZE 0.3, DECAY 0.45, DAMP 0.1", dict(size=0.3, decay=0.45, damp=0.1)),
    ("03_huge_dark", "Huge and dark, long: SIZE 1.0, DECAY 0.9, DAMP 0.6, PREDELAY 80 ms",
     dict(size=1.0, decay=0.9, damp=0.6, pred=0.16)),
    ("04_no_diffusion", "DIFFUSION 0: the tank's echoes heard (Plateau's diffusion at zero)", dict(diff=0.0, decay=0.7)),
    ("05_wobble", "Deep, fast modulation: MSPD 0.7, MDEP 1.0 (the pitch-bending tank)", dict(mspd=0.7, mdep=1.0, decay=0.8)),
    ("06_lowcut_tank", "Tank LOW CUT up: a thin, airy tail (TLOW 0.5, LOCUT 0.3)", dict(tlocut=0.5, locut=0.3, decay=0.8)),
]


def main(out: str) -> None:
    o = Path(out)
    o.mkdir(parents=True, exist_ok=True)
    x = source()
    tail = np.zeros(int(4.0 * SR))
    xs = np.concatenate([x, tail])
    notes = ["# PLATEAU auditions\n", "Each file: the sources dry (left = right), then the same through PLATEAU, MIX 50 %.\n"]
    for name, title, kw in SETTINGS:
        p = Plateau(**kw)
        L, R = p.run(xs, xs)
        dl, dr = np.concatenate([x, np.zeros(SR // 2)]), np.concatenate([x, np.zeros(SR // 2)])
        wav2(o / f"plateau_{name}.wav", np.concatenate([dl, L]), np.concatenate([dr, R]))
        notes.append(f"- `plateau_{name}.wav`: {title}\n")
        print(name, flush=True)
    # HOLD: a chord in, then frozen while the input carries on (the freeze holds what was in)
    l, _ = FA._line(notes=(48, 55, 60, 64), dur=0.5)
    p = Plateau(size=0.8, decay=0.7, wet=1.0, dry=0.6)
    a = p.run(l, l)
    p.set(hold=True)
    z = np.zeros(int(5 * SR))
    b = p.run(z, z)
    wav2(o / "plateau_07_hold.wav", np.concatenate([a[0], b[0]]), np.concatenate([a[1], b[1]]))
    notes.append("- `plateau_07_hold.wav`: four notes, then HOLD: the tank sustains them (freeze)\n")
    # TUNED: plucks through a tank tuned to C3, then G3
    pl, _ = FA._plucks()
    outs = []
    for n in (48, 55, 60):
        p = Plateau(tuned=True, note=n, decay=0.85, wet=1.0, dry=0.3, mdep=0.0)
        outs.append(p.run(np.concatenate([pl, np.zeros(SR)]), np.concatenate([pl, np.zeros(SR)])))
    wav2(o / "plateau_08_tuned.wav", np.concatenate([u[0] for u in outs]), np.concatenate([u[1] for u in outs]))
    notes.append("- `plateau_08_tuned.wav`: TUNED: the tank's loop at C3, G3, C4 (the reverb as a pitched resonator)\n")
    (o / "LISTEN.md").write_text("".join(notes))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/plateau")
