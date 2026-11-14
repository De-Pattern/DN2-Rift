"""ORGAN's reference: Ravel's own C, compiled natively at the DN2's 48 kHz and 32-sample blocks.

    python3 scripts/organ_ref.py RAVEL_CHECKOUT [--write]

Builds scripts/organ_ref/harness.c around Ravel's organ_note/organ_render (rv_synth.c, copied
unchanged from RAVEL_CHECKOUT) and rv_math.h / rv_dsp.h / rv_organ.h (RV_DT and RV_NYQ set to
48 kHz), renders CASES and prints each output's sha256; --write records them in
src/dnfw/organ/reference.json, which test_organ_ref checks ref.py against, bit for bit.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REF = ROOT / "src" / "dnfw" / "organ" / "reference.json"
SEED = 0x1234567
SECS = 0.25


def _eff(stop, ranks, chiff=40, speech=50, spread=40, air=25, wind=30, trem=0, rate=60, cel=0):
    r = [0] * 7
    for k, v in ranks.items():
        r[k] = v
    return [stop, *r, chiff, speech, spread, air, wind, trem, rate, cel]


R16, R8, R4, R223, R2, R135, R1 = range(7)
# Ravel's presets (rv_presets.c, as the engine document lists them), one extreme, one low note
CASES = {
    "INFINITE": (_eff(1, {R8: 110, R4: 80, R223: 50, R2: 60}, chiff=55, speech=62, spread=70, air=40, wind=40), 60),
    "PLENUM": (_eff(2, {R16: 70, R8: 110, R4: 90, R223: 60, R2: 80, R135: 40, R1: 60}, chiff=30), 48),
    "VOX CELESTE": (_eff(3, {R8: 110, R4: 30}, trem=30, cel=70, chiff=15), 55),
    "FLUTE 4'": (_eff(0, {R8: 50, R4: 110}, chiff=85, speech=40, air=30), 72),
    "TROMPETTE": (_eff(4, {R8: 110, R4: 60}, chiff=20, speech=30), 50),
    "extremes": (_eff(4, {k: 127 for k in range(7)}, chiff=127, speech=0, spread=127, air=127, wind=127, trem=127,
                      rate=127, cel=127), 96),
    "low": (_eff(2, {R16: 127}, speech=127), 24),
}


def build(ravel: Path, work: Path) -> Path:
    app = ravel / "firmware" / "app"
    for h in ("rv_math.h", "rv_organ.h"):
        (work / h).write_text((app / h).read_text(encoding="utf-8"), encoding="utf-8")
    dsp = (app / "rv_dsp.h").read_text(encoding="utf-8")
    dsp = dsp.replace("#define RV_DT (1.0f / 44100.0f)", "#define RV_DT (1.0f / 48000.0f)")
    dsp = dsp.replace("#define RV_NYQ 22050.0f", "#define RV_NYQ 24000.0f")
    assert "48000.0f" in dsp and "24000.0f" in dsp
    (work / "rv_dsp.h").write_text(dsp, encoding="utf-8")
    syn = (app / "rv_synth.c").read_text(encoding="utf-8")
    a = syn.index("/* -------------------------------------------------------------- ORGAN --- */")
    b = re.search(r"\n/\* -+ MONO -+ \*/", syn[a:]).start() + a
    (work / "organ_body.c").write_text(syn[a:b] + "\n", encoding="utf-8")
    (work / "harness.c").write_text((ROOT / "scripts" / "organ_ref" / "harness.c").read_text(), encoding="utf-8")
    exe = work / "harness"
    subprocess.run(["gcc", "-O2", "-std=gnu99", "-ffp-contract=off", "-o", str(exe), str(work / "harness.c"), "-lm"],
                   check=True)
    return exe


def render(exe: Path, eff, note) -> bytes:
    return subprocess.run([str(exe), hex(SEED), str(note), str(SECS), *map(str, eff)], capture_output=True,
                          check=True).stdout


def main(argv) -> int:
    ravel = Path(argv[0])
    rev = subprocess.run(["git", "-C", str(ravel), "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True).stdout.strip()
    with tempfile.TemporaryDirectory() as tmp:
        exe = build(ravel, Path(tmp))
        out = {n: hashlib.sha256(render(exe, e, nt)).hexdigest() for n, (e, nt) in CASES.items()}
    for n, h in out.items():
        print(f"{n:12s} {h}")
    if "--write" in argv:
        REF.write_text(json.dumps({"ravel": rev, "seed": SEED, "seconds": SECS, "sha256": out}, indent=1) + "\n")
        print("wrote", REF.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
