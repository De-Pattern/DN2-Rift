"""ORGAN on the SHARC's arithmetic (src/dnfw/organ/live.py) against Ravel's C (ref.py, itself
bit-exact to the compiled C): the divides made the SHARC's way move the output by less than
120 dB below the signal over half a second (measured 2026-11-14: 138 to 155 dB over a second)."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

from dnfw.organ import live as L
from dnfw.organ import ref as R

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("organ_ref", ROOT / "scripts" / "organ_ref.py")
OR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OR)
TAB = R.tables()


def _render(M, eff, note, secs=0.5, seed=0x1234567):
    o = M.Organ(TAB, seed)
    o.note(eff)
    f = M.note_hz(note)
    return np.concatenate([o.render(eff, f) for _ in range(int(secs * 48000 / 32))]).astype(float)


@pytest.mark.parametrize("name", list(OR.CASES))
def test_the_sharcs_divide_is_inaudible(name):
    eff, note = OR.CASES[name]
    a, b = _render(R, eff, note), _render(L, eff, note)
    err = 10 * np.log10(np.sum(a ** 2) / max(np.sum((a - b) ** 2), 1e-30))
    assert err > 120.0, err


def test_only_the_divides_differ():
    src = (ROOT / "src" / "dnfw" / "organ" / "live.py").read_text()
    body = src[src.index("# -- rv_math.h"):]
    import re
    divs = [ln for ln in body.splitlines() if re.search(r"[^/]/ [^/]", ln) and "F(1.0 / 2147483648.0)" not in ln
            and not re.search(r"F\(F?\(?[0-9.]+\)? / F\(", ln) and not ln.strip().startswith(("#", '"'))]
    assert divs == ["        self.k = F(F(1.0) / (F(0.05) if q < F(0.05) else F(q)))"], divs   # q is always 5
