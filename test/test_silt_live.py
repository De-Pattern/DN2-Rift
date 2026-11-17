"""SILT's float32 voice (live.py) against the audition model the owner approved (model.py).

Not bit-exact (the DSP's primitives against libm, in feedback loops): the same level and the
same spectral envelope over a held note, for each material and the ensemble modes, to within
what the model itself varies by from one random seed to another (the noisy gestures and the
drips are chaotic: a last-bit difference picks other random events). Every output finite and
inside the soft clip."""
import numpy as np
import pytest

from dnfw.silt import live as L
from dnfw.silt import model as M

NOTES = [(0.0, 48, 0.9, 0.8)]
SEEDS = (0x3698CF1D, 0x5B05B057, 0x7F6FE491)
CASES = {
    "fiber_bow": dict(MAT="FIBER"),
    "fiber_mass8": dict(MAT="FIBER", MODE="MASS-8", QUAL="NORMAL", SPREAD=70, VOICES=127),
    "fiber_scrape": dict(MAT="FIBER", GEST="SCRAPE", PRESS=100, SCRAP=80, INST=90),
    "skin_stacc": dict(MAT="SKIN", GEST="STACC", SNAP=104, VISC=28, PRESS=70, TENS=40, VOICES=0),
    "silt_fract": dict(MAT="SILT", MODE="SWARM", GEST="FRACT", DENS=64, COHE=100),
    "fluid_bow": dict(MAT="FLUID", GEST="BOW", DENS=56, VISC=26),
}


def bands(x):
    X = np.abs(np.fft.rfft(x * np.hanning(len(x)))) ** 2
    f = np.fft.rfftfreq(len(x), 1 / 48000)
    e = np.logspace(np.log10(60), np.log10(16000), 9)
    return np.array([10 * np.log10(X[(f >= e[i]) & (f < e[i + 1])].sum() + 1e-12) for i in range(8)])


@pytest.mark.parametrize("name", list(CASES))
def test_live_is_the_model(name):
    kw = CASES[name]
    a = M.play(M.panel(**kw), NOTES, 1.0)
    b = L.render(L.panel(**kw), NOTES, 1.0).astype(float)
    assert np.isfinite(b).all() and np.abs(b).max() <= 1.0
    ra, rb = np.sqrt(np.mean(a ** 2)), np.sqrt(np.mean(b ** 2))
    tol_db, tol_b = 1.0, np.full(8, 2.0)
    for sd in SEEDS:                                  # the model against itself, other seeds
        c = M.play(M.panel(**kw), NOTES, 1.0, seed=sd)
        tol_db = max(tol_db, abs(20 * np.log10(np.sqrt(np.mean(c ** 2)) / ra)) + 0.5)
        tol_b = np.maximum(tol_b, np.abs(bands(a) - bands(c)) + 1.0)
    assert abs(20 * np.log10(rb / ra)) < tol_db
    d = np.abs(bands(a) - bands(b))
    assert (d < tol_b).all(), (d, tol_b)


def test_the_comparison_sees_a_wrong_voice():
    """negative control: a different material by the same measure fails it"""
    a = M.play(M.panel(MAT="FIBER"), NOTES, 1.0)
    b = L.render(L.panel(MAT="SKIN"), NOTES, 1.0).astype(float)
    d = np.abs(bands(a) - bands(b))
    ra, rb = np.sqrt(np.mean(a ** 2)), np.sqrt(np.mean(b ** 2))
    assert d.max() >= 4.0 or abs(20 * np.log10(rb / ra)) >= 1.0


def test_deep_is_four_players():
    assert L.QN_MASS == (2, 3, 4) == (2, 3, L.NSEC_DEEP)


def test_a_slot_becoming_silt_clears_its_lines_then_plays_the_waiting_note():
    """docs/silt-dsp.md: 24 blocks of 512 words; a note meanwhile waits; then the voice is a
    fresh one's, block for block"""
    P = L.panel(MAT="FIBER")
    v = L.Voice()
    for buf in v.lines():
        buf[:] = L.F(1.5)                      # garbage
    v.become()
    v.note(P, 48, 0.9)
    out = [v.block(P).copy() for _ in range(24)]
    assert all((o == 0).all() for o in out)
    assert all((b == 0).all() for b in v.lines())
    ref = L.Voice()
    ref.note(P, 48, 0.9)
    for _ in range(40):
        assert (v.block(P) == ref.block(P)).all()


def test_the_clear_test_sees_garbage():
    """negative control: without the clear, the garbage is heard"""
    P = L.panel(MAT="FIBER")
    v, ref = L.Voice(), L.Voice()
    for buf in v.lines():
        buf[:] = L.F(1.5)
    v.note(P, 48, 0.9)
    ref.note(P, 48, 0.9)
    assert any((v.block(P) != ref.block(P)).any() for _ in range(40))


def test_a_released_voice_rests_and_a_note_wakes_it():
    P = L.panel(MAT="FIBER")
    v = L.Voice()
    assert v.rest
    v.note(P, 48, 0.9)
    for _ in range(20):
        v.block(P)
    v.block(P, off=True)
    n = 0
    while not v.rest and n < 2000:
        v.block(P)
        n += 1
    assert v.rest and 500 < n < 1000          # about half a second of release
    assert (v.block(P) == 0).all()
    v.note(P, 55, 0.9)
    assert any((v.block(P) != 0).any() for _ in range(10))


def test_another_material_fades_clears_then_plays():
    """a trig of another MAT on a sounding voice: one faded block, 24 silent blocks of clearing,
    then the new note from fresh lines (owner, 2026-11-15: page 4 per trig, without clicks)"""
    A, B = L.panel(MAT="FIBER"), L.panel(MAT="SKIN", GEST="STACC")
    v = L.Voice()
    v.note(A, 48, 0.9)
    for _ in range(50):
        last = v.block(A).copy()
    v.note(B, 55, 0.9)
    faded = v.block(B)
    assert abs(faded[-1]) < abs(last).max() * 0.1 + 1e-6
    assert all((v.block(B) == 0).all() for _ in range(24))
    assert all((b == 0).all() for b in v.lines())
    assert any((v.block(B) != 0).any() for _ in range(10))


def test_the_slot_voice_reads_the_dn2s_frame():
    knobs = [L.DEFAULTS[c] for c in L.CONTROLS[:24]] + [
        L.option_knob(L.DEFAULTS[c], len(L.CHOICES[c])) for c in L.CONTROLS[24:]]
    assert L.eff_of(knobs)[24:] == [float(L.DEFAULTS[c]) for c in L.CONTROLS[24:]]
    v = L.SlotVoice(3)
    out = [v.dsp_block(knobs, k == 0, 48.0, 100, k == 30) for k in range(60)]
    assert np.abs(np.concatenate(out)).max() > 0.01
