"""Write SMEAR's stage, csrc/waverider/sharc/smear.asm (docs/smear.md, RIFT v0.16).

    python scripts/gen_smear_asm.py [--no-resolve]

The program is `dnfw.smear.stage.program` at dnfw.waverider.dsp's addresses: entered from
smp.asm's tail, on to fascia.asm. Assemble it with `scripts/gen_waverider_sharc.py --assemble`.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from dnfw.smear import stage as SG        # noqa: E402
from dnfw.waverider import dsp            # noqa: E402

OUT = ROOT / "csrc" / "waverider" / "sharc" / "smear.asm"


def build() -> str:
    return SG.program(dsp.smear_layout(), dsp.FSC_SW)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-resolve", action="store_true")
    a = ap.parse_args(argv)
    text = build()
    if not a.no_resolve:
        import sharc_resolve_jumps as R  # noqa: PLC0415  (selas)
        with tempfile.TemporaryDirectory() as tmp:
            text, be, offs = R.resolve(text, dsp.SMEAR_SW, pathlib.Path(tmp))
        print(f"resolved at sw {dsp.SMEAR_SW:#x}: {len(offs)} instructions, {len(be)} bytes")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    n = sum(1 for ln in text.splitlines() if ln.startswith("      ") and not ln.strip().startswith("//"))
    print(f"wrote {OUT.relative_to(ROOT)}: {n} instructions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
