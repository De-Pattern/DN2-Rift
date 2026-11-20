"""Write THOLET's six strikes, src/dnfw/tholet/hits.json (docs/tholet.md).

    python scripts/gen_tholet_hits.py [VCSL_KAWAI_SUSTAINS_DIR]

Each strike is the first 50 ms of a Kawai grand note from VCSL (CC0, github.com/sgossner/VCSL),
from its onset, with the model's slight decay and end fade (dnfw.tholet.model.load_hit), then
resampled to 24 kHz and stored as 8-bit G.711 mu-law: 1,200 bytes a strike, 7,200 in all. The
build reads the JSON only, so it needs neither VCSL nor numpy's audio.
"""
from __future__ import annotations

import json
import pathlib
import sys

import numpy as np

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from dnfw.tholet import model as M      # noqa: E402

OUT = ROOT / "src" / "dnfw" / "tholet" / "hits.json"
RATE, N = 24000, 1200


def mulaw_encode(x: np.ndarray) -> bytes:
    """G.711 mu-law of x in [-1, 1] (the standard's segments, bias 0x84)"""
    s = np.clip(np.round(x * 32767.0), -32767, 32767).astype(np.int32)
    out = bytearray()
    for v in s:
        sign = 0x80 if v < 0 else 0
        m = min(-v if v < 0 else v, 32635) + 0x84
        exp = 7
        while exp > 0 and not (m & (0x4000 >> (7 - exp))):
            exp -= 1
        mant = (m >> (exp + 3)) & 0x0F
        out.append(~(sign | (exp << 4) | mant) & 0xFF)
    return bytes(out)


def mulaw_decode(b: int) -> float:
    b = ~b & 0xFF
    sign, exp, mant = b & 0x80, (b >> 4) & 7, b & 0x0F
    m = (((mant << 3) + 0x84) << exp) - 0x84
    return (-m if sign else m) / 32768.0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        M.VCSL = pathlib.Path(argv[0])
    hits, notes = [], []
    for k in range(len(M.HITS)):
        x, note = M.load_hit(k)
        t = np.arange(N) * (M.FS / RATE)
        y = np.interp(t, np.arange(len(x)), x, right=0.0)
        y[-24:] *= np.linspace(1, 0, 24)
        hits.append(mulaw_encode(y).hex())
        notes.append(note)
    OUT.write_text(json.dumps({"note": "written by scripts/gen_tholet_hits.py from VCSL's Kawai grand (CC0); do not edit",
                               "rate": RATE, "n": N, "names": list(M.HIT_NAMES), "notes": notes,
                               "hits": hits}) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(ROOT)}: {len(hits)} strikes x {N} bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
