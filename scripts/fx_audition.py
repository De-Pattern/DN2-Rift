"""Render RIFT's new effects' reference models for listening (docs/fx-platform.md).

    PYTHONPATH=src python3 scripts/fx_audition.py OUTDIR

One WAV an effect, each a tour: the same few sources (FASCIA pass-3 patches, a drum loop, a
synth line, plucks) dry, then through the effect at several settings, a short silence between.
OUTDIR/LISTEN.md says what each section is. 48 kHz mono 16-bit (the inserts run per voice,
mono, docs/fx-platform.md §1).
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import numpy as np

from dnfw.fx import chrono as C
from dnfw.fx import funcgen as FG
from dnfw.fx import lpg as L
from dnfw.fx import reson as R
from dnfw.fx import resonator as RS
from dnfw.fx import warp as W
from dnfw.fx.common import RATE, write_wav

SR = int(RATE)
GAP = np.zeros(int(0.35 * SR))


def _fascia(name: str) -> np.ndarray:
    spec = importlib.util.spec_from_file_location("fa", Path(__file__).with_name("fascia_audition.py"))
    fa = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fa)
    p, evs, secs, _ = fa.PATCHES[name]
    x = fa.R.render_notes(p, evs, min(secs, 3.2))
    return x / max(np.max(np.abs(x)), 1e-9) * 0.5, [int(t * SR) for t, *_ in evs]


def _drums(bars: int = 2, bpm: float = 118.0) -> tuple[np.ndarray, list[int]]:
    """A plain kit: kick, snare, hats, 16ths."""
    step = int(SR * 60 / bpm / 4)
    n = step * 16 * bars
    x = np.zeros(n + SR // 2)
    rng = np.random.default_rng(7)
    hits = []
    for s in range(16 * bars):
        k = s * step
        t = np.arange(int(0.35 * SR)) / SR
        if s % 4 == 0:
            f = 50 + 120 * np.exp(-t * 35)
            x[k:k + len(t)] += 0.8 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
            hits.append(k)
        if s % 8 == 4:
            m = int(0.2 * SR)
            x[k:k + m] += (0.4 * rng.standard_normal(m) + 0.3 * np.sin(2 * np.pi * 190 * t[:m])) * np.exp(-t[:m] * 22)
            hits.append(k)
        m = int(0.05 * SR)
        hat = rng.standard_normal(m)
        hat = np.diff(hat, prepend=0)
        x[k:k + m] += (0.12 if s % 2 else 0.06) * hat * np.exp(-np.arange(m) / SR * 80)
    return x * 0.6, hits


def _line(notes=(45, 45, 52, 48, 45, 57, 55, 52), dur: float = 0.25) -> tuple[np.ndarray, list[int]]:
    """A monosynth line: a saw through a one-pole low-pass, a short envelope."""
    out, ons = [], []
    pos = 0
    for nt in notes:
        n = int(dur * SR)
        f = 440 * 2 ** ((nt - 69) / 12)
        ph = (np.arange(n) * f / SR) % 1
        s = 2 * ph - 1
        y = np.zeros(n)
        a = 0.0
        for i in range(n):
            a += (s[i] - a) * 0.15
            y[i] = a
        y *= np.minimum(1, np.arange(n) / 100) * np.exp(-np.arange(n) / SR * 4)
        out.append(0.4 * y)
        ons.append(pos)
        pos += n
    return np.concatenate(out + [np.zeros(SR // 2)]), ons


def _plucks() -> tuple[np.ndarray, list[int]]:
    x = np.zeros(int(3.0 * SR))
    ons = []
    rng = np.random.default_rng(3)
    for k, t in enumerate((0.0, 0.5, 1.0, 1.25, 1.75, 2.25)):
        i = int(t * SR)
        m = 600
        x[i:i + m] += 0.6 * rng.standard_normal(m) * np.exp(-np.arange(m) / 90)
        ons.append(i)
    return x, ons


def tour(sections) -> np.ndarray:
    out = []
    for x in sections:
        out += [np.asarray(x), GAP]
    return np.concatenate(out)


def main(out: str) -> None:
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bell, bell_on = _fascia("01_tubular_bell")
    snare, snare_on = _fascia("20_snare_wires")
    drums, drum_on = _drums()
    line, line_on = _line()
    plucks, pluck_on = _plucks()
    guide = ["# RIFT effects: what to listen for", "",
             "Reference models (src/dnfw/fx), per voice and mono as the inserts will run. Each file is a",
             "tour: the sections play in the order listed, a short silence between. Levels are not",
             "matched across sections; nothing here is the final sound, the knobs move.", ""]

    def run(name, title, rows):
        secs, lines = [], [f"## {name}.wav: {title}", ""]
        for k, (label, y) in enumerate(rows, 1):
            assert np.all(np.isfinite(y)), (name, label)
            secs.append(y / max(np.max(np.abs(y)), 1e-9) * 0.7)
            lines.append(f"{k}. {label}")
        write_wav(out / f"{name}.wav", tour(secs))
        guide.extend(lines + [""])
        print(name, "ok")

    # RESON: the six profiles, then the page's knobs
    rows = [("drums dry", drums)]
    for prof in R.PROFILE_NAMES:
        rows.append((f"drums, RESON {prof} (Viscera's profile)", R.Reson().process(drums, R.params(prof), drum_on)))
    rows += [("synth line dry", line),
             ("synth line, THROAT (vocoded through its own output)", R.Reson().process(line, R.params("THROAT"), line_on)),
             ("synth line, GLASS, RESO 100, SHFT 80", R.Reson().process(line, R.params("GLASS", RESO=100, SHFT=80), line_on)),
             ("FASCIA bell dry", bell),
             ("FASCIA bell, LIQ MEM, LIQ 110 (the bands drift)", R.Reson().process(bell, R.params("LIQ MEM", LIQ=110), bell_on)),
             ("FASCIA snare wires, DUST, DROP 90", R.Reson().process(snare, R.params("DUST", DROP=90), snare_on)),
             ("plucks, PING mode, RESO 120 (rings from each note)",
              R.Reson().process(plucks, R.params("DUST", MODE="PING", RESO=120, DUST=0, TRIG="NOTES"), pluck_on))]
    run("reson", "RESON, the Viscera filterbank / vocoder / ping", rows)

    rows = [("plucks dry", plucks)]
    for ch, br, fb in (("MAJ", 80, 110), ("MIN7", 60, 120), ("P5", 110, 125), ("MI11", 40, 118), ("OCT", 127, 126)):
        rows.append((f"plucks, RSNTR {ch}, BRIT {br}, FDBK {fb}",
                     RS.Resonator().process(plucks, RS.params(CHRD=ch, BRIT=br, FDBK=fb, KEYT=0, ROOT=50))))
    rows += [("drums dry", drums),
             ("drums, RSNTR MIN, ENVM 127 (rings harder as the input is louder)",
              RS.Resonator().process(drums, RS.params(CHRD="MIN", ENVM=127, FDBK=100, ROOT=45, KEYT=0))),
             ("drums, RSNTR DIM, DRIV 110", RS.Resonator().process(drums, RS.params(CHRD="DIM", DRIV=110, ROOT=40, KEYT=0))),
             ("FASCIA bell, RSNTR MAJ9 a fifth below", RS.Resonator().process(bell, RS.params(CHRD="MAJ9", ROOT=53, KEYT=0, MIX=60)))]
    run("rsntr", "RSNTR, the P-6-style resonator", rows)

    rows = [("synth line dry", line)]
    for sh, sb, fb, dep, rg in ((76, 0, 0, 0, 64), (52, 127, 0, 0, 64), (64, 64, 0, 0, 90), (70, 0, 110, 0, 40),
                                (68, 0, 0, 110, 20)):
        rows.append((f"synth line, WARP SHFT {sh}, SBND {sb}, FDBK {fb}, DEP {dep}, RANG {rg}",
                     W.Warp().process(line, W.params(SHFT=sh, SBND=sb, FDBK=fb, DEP=dep, RANG=rg, MIX=127))))
    rows += [("FASCIA bell dry", bell),
             ("FASCIA bell, WARP up, KEYT 127 (the shift follows the note)",
              W.Warp().process(bell, W.params(SHFT=90, KEYT=127, RANG=50, MIX=110))),
             ("drums, WARP barber-pole (FDBK 120, slow LFO)",
              W.Warp().process(drums, W.params(SHFT=66, FDBK=120, DEP=60, SPD=20, RANG=60, MIX=110)))]
    run("warp", "WARP, the frequency shifter (after the Tonverk's Frequency Warper)", rows)

    rows = [("synth line dry", line)]
    for tu, wi, fb, dep, j in ((96, 60, 0, 0, 20), (32, 80, 0, 0, 20), (83, 40, 90, 0, 30), (127, 100, 110, 40, 60),
                               (64, 20, 0, 90, 0)):
        rows.append((f"synth line, CHRONO TUNE {C.semitones(tu):+.0f}, WIN {wi}, FDBK {fb}, DEP {dep}, JITR {j}",
                     C.Chrono().process(line, C.params(TUNE=tu, WIN=wi, FDBK=fb, DEP=dep, JITR=j, MIX=110))))
    rows += [("FASCIA bell, CHRONO +12 shimmer (FDBK 100, LPF 90)",
              C.Chrono().process(bell, C.params(TUNE=96, FDBK=100, LPF=90, WIN=90, MIX=90))),
             ("drums, CHRONO -7, short WIN", C.Chrono().process(drums, C.params(TUNE=45, WIN=15, MIX=110)))]
    run("chrono", "CHRONO, the granular pitch shifter (after the Tonverk's Chrono Pitch)", rows)

    # LPG: one note at a time through the gate (a voice per note, as the filter runs)
    def lpg_seq(src_notes, p, hold=0.08, step=0.3):
        y = np.zeros(int((len(src_notes) * step + 1.5) * SR))
        for k, nt in enumerate(src_notes):
            n = int(1.5 * SR)
            f = 440 * 2 ** ((nt - 69) / 12)
            s = 0.4 * ((np.arange(n) * f / SR) % 1 * 2 - 1)
            g = np.zeros(n)
            g[:int(hold * SR)] = 1
            i = int(k * step * SR)
            y[i:i + n] += L.LPG().process(s, p, g)
        return y
    notes = (48, 55, 60, 58, 51, 63)
    rows = [(f"saw notes, LPG COMBO, DEC {d}, RESO {r}", lpg_seq(notes, L.params(DEC=d, REL=d, RESO=r)))
            for d, r in ((30, 0), (60, 20), (85, 60), (50, 110))]
    rows += [("saw notes, LPG LP only", lpg_seq(notes, L.params(TYPE="LP", DEC=60, REL=60))),
             ("saw notes, LPG VCA only", lpg_seq(notes, L.params(TYPE="VCA", DEC=60, REL=60)))]
    run("lpg", "LPG, the low-pass gate filter type (the stock filter page's knobs)", rows)

    # FUNC: as an amplitude and a cutoff on a drone, then as a percussive envelope
    n = 5 * SR
    drone = 0.4 * ((np.arange(n) * 110 / SR) % 1 * 2 - 1)

    def cutoff(x, env, lo=80.0, hi=6000.0):
        y, a = np.zeros(len(x)), 0.0
        for i in range(len(x)):
            c = 1 - np.exp(-2 * np.pi * (lo * (hi / lo) ** env[i]) / SR)
            a += (x[i] - a) * c
            y[i] = a
        return y
    rows = []
    for rise, fall, resp in ((60, 60, 64), (40, 80, 127), (80, 40, 0), (20, 20, 100)):
        e = FG.FuncGen().process(n, FG.params(RISE=rise, FALL=fall, RESP=resp, CYCL=127))
        rows.append((f"drone, FUNC cycling on the cutoff: RISE {rise}, FALL {fall}, RESP {resp}", cutoff(drone, e)))
    gate = np.zeros(n)
    for t in np.arange(0, 4.5, 0.5):
        gate[int(t * SR):int(t * SR) + 200] = 1
    for resp in (0, 64, 127):
        e = FG.FuncGen().process(n, FG.params(RISE=5, FALL=70, RESP=resp), gate)
        rows.append((f"drone, FUNC as a percussive envelope (RISE 5, FALL 70), RESP {resp}", drone * e))
    run("func", "FUNC, the looping function generator (as a modulation source)", rows)

    (out / "LISTEN.md").write_text("\n".join(guide))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "out/fx-audition")
