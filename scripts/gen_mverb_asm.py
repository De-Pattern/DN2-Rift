"""Write the master reverb, csrc/waverider/sharc/mverb.asm (RIFT v0.21).

    python scripts/gen_mverb_asm.py [--no-resolve]

The program is `dnfw.mverb.program.program`, entered from the stock FX function in the stock reverb
core's place. Assemble it with `scripts/gen_waverider_sharc.py --assemble`.
"""

from __future__ import annotations

import argparse
import pathlib
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from dnfw.mverb import program as MP       # noqa: E402
from dnfw.waverider import dsp            # noqa: E402

OUT = ROOT / "csrc" / "waverider" / "sharc" / "mverb.asm"


def build() -> str:
    return MP.program(MP.layout())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-resolve", action="store_true")
    a = ap.parse_args(argv)
    text = build()
    if not a.no_resolve:
        import sharc_resolve_jumps as R  # noqa: PLC0415  (selas)
        with tempfile.TemporaryDirectory() as tmp:
            text, be, offs = R.resolve(text, dsp.MVERB_SW, pathlib.Path(tmp))
        print(f"resolved at sw {dsp.MVERB_SW:#x}: {len(offs)} instructions, {len(be)} bytes")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    from dnfw.smear import program as _SPw   # noqa: PLC0415
    _SPw.write_ddr_json()                   # the link's tables, for the numpy-free build (smear/ddr.json)
    n = sum(1 for ln in text.splitlines() if ln.startswith("      ") and not ln.strip().startswith("//"))
    print(f"wrote {OUT.relative_to(ROOT)}: {n} instructions")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
