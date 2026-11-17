"""LIGATURE's voice (dnfw.ligature.live): every patch sounds, stays bounded and finite, rests after its
note-off, and its knobs at 64 play the patch as WEFT made it."""
import numpy as np
import pytest

from dnfw.ligature import live as L


def knobs(pk, **kw):
    kn = [L.DEFAULTS[c] for c in L.CONTROLS]
    kn[0] = (2 * pk + 1) * 128 // (2 * L.NP)
    for c, v in kw.items():
        kn[L.CONTROLS.index(c)] = v
    return kn


@pytest.mark.parametrize("pk", range(L.NP))
def test_every_patch_sounds_bounded(pk):
    y = L.render(knobs(pk), [(0.0, 48, 100, 0.4)], 0.6)
    assert np.isfinite(y).all() and np.abs(y).max() <= 0.6 + 1e-6 and np.abs(y).max() > 0.01


def test_the_patch_knob_reads_equal_spans():
    seen = [L.patch_of(k) for k in range(128)]
    assert seen[0] == 0 and seen[127] == L.NP - 1 and sorted(set(seen)) == list(range(L.NP))


def test_a_released_note_rests():
    v = L.SlotVoice(0)
    kn = knobs(L.CONTROLS and 0)
    v.dsp_block(kn, True, 48.0, 100, False)
    for _ in range(5):
        v.dsp_block(kn, False, 48.0, 100, False)
    v.dsp_block(kn, False, 48.0, 100, True)
    for _ in range(3000):
        v.dsp_block(kn, False, 48.0, 100, False)
        if not v.on:
            break
    assert not v.on


def test_feedback_is_a_block_late():
    """TANGLE's block 2 reads block 6 (later): what 6 made the block before"""
    rows, _o, _m = L.patch_rows([n for n, *_r in L.PATCHES].index("TANGLE"))
    assert rows[1][3] == 6
