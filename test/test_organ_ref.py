"""ORGAN's reference (src/dnfw/organ/ref.py) against Ravel's own C at 48 kHz: every
case's output must hash to what scripts/organ_ref.py recorded from the compiled C, bit for bit."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

from dnfw.organ import ref as L

ROOT = Path(__file__).resolve().parent.parent
REF = json.loads((ROOT / "src" / "dnfw" / "organ" / "reference.json").read_text())
spec = importlib.util.spec_from_file_location("organ_ref", ROOT / "scripts" / "organ_ref.py")
OR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(OR)
TAB = L.tables()


def _render(eff, note, secs, seed):
    o = L.Organ(TAB, seed)
    o.note(eff)
    f = L.note_hz(note)
    n = int(secs * L.FS / L.SUB)
    return np.concatenate([o.render(eff, f) for _ in range(n)])


@pytest.mark.parametrize("name", list(OR.CASES))
def test_ref_is_ravels_organ_bit_for_bit(name):
    eff, note = OR.CASES[name]
    y = _render(eff, note, REF["seconds"], REF["seed"])
    assert hashlib.sha256(y.astype("<f4").tobytes()).hexdigest() == REF["sha256"][name]


def test_the_tables_are_ravels():
    assert TAB.shape == (5, 3, 256) and TAB.min() >= -128 and TAB.max() <= 127


def test_a_rank_above_the_band_is_left_out_and_silence_is_silent():
    eff = [0] + [0] * 7 + [0, 50, 0, 0, 0, 0, 60, 0]           # no rank, no chiff, no air
    y = _render(eff, 60, 0.05, 1)
    assert not np.any(y)
    eff = [2] + [0, 0, 0, 0, 0, 0, 127] + [0, 50, 0, 0, 0, 0, 60, 0]   # 1' at the top: above 0.45 fs
    assert not np.any(_render(eff, 120, 0.05, 1))
