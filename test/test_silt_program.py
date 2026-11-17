"""SILT's DSP program (run mode) is live.SlotVoice bit for bit: every material, gesture family and
ensemble mode, notes, velocities, note-offs, moving knobs, a material change (its fade and the
lines' clear), a release to rest and a note after it. The SHARC runner's `silt` part holds the
assembled code to this run mode."""
import numpy as np
import pytest

from dnfw.silt import bench as B
from dnfw.silt import live as L
from dnfw.silt import program as P

CASES = {
    "fiber": dict(MAT="FIBER", VOICES=0),
    "fiber_strands": dict(MAT="FIBER", VOICES=90, SPREAD=40),
    "fiber_mass_deep": dict(MAT="FIBER", MODE="MASS", QUAL="DEEP", SPREAD=70, VOICES=127),
    "fiber_mass8_cloud": dict(MAT="FIBER", MODE="MASS-8", QUAL="NORMAL", SPREAD=70, VOICES=127, DENS=70),
    "fiber_scrape_stress": dict(MAT="FIBER", GEST="SCRAPE", PRESS=110, SCRAP=80, INST=90, GRAIN=100, DENS=60, PART=90),
    "fiber_spicc_soft": dict(MAT="FIBER", GEST="SPICC", MODE="MASS", SHAPE="SOFT"),
    "fiber_legno_free": dict(MAT="FIBER", GEST="LEGNO", MODE="MASS", LOOP="FREE", ROUGH=70),
    "fiber_gliss_wide_exp": dict(MAT="FIBER", GEST="GLISS", MODE="MASS", DIST="WIDE", GLISS=0, SHAPE="EXP"),
    "fiber_gliss_asym": dict(MAT="FIBER", GEST="GLISS", MODE="MASS", DIST="ASYM", GLISS=127),
    "fiber_swell_scale": dict(MAT="FIBER", GEST="SWELL", MODE="MASS", TUNE="SCALE", SPREAD=100),
    "fiber_quake_chaotic": dict(MAT="FIBER", GEST="QUAKE", SHAPE="CHAOTIC", TUNE="MICRO", MORPH=60),
    "fiber_fract_morph": dict(MAT="FIBER", GEST="FRACT", MODE="MASS", MORPH=50),
    "fiber_stacc_loop": dict(MAT="FIBER", GEST="STACC", LOOP="1/16"),
    "skin_stacc": dict(MAT="SKIN", GEST="STACC", SNAP=104, VISC=28, PRESS=70, TENS=40, VOICES=0, DENS=60),
    "skin_bow": dict(MAT="SKIN", GEST="BOW", VOICES=60, PART=90),
    "silt_swarm_fract": dict(MAT="SILT", MODE="SWARM", GEST="FRACT", DENS=64, COHE=100),
    "fluid_bow": dict(MAT="FLUID", GEST="BOW", DENS=56, VISC=26),
    "fluid_stacc_mass": dict(MAT="FLUID", GEST="STACC", DENS=100, MODE="MASS"),
}


@pytest.mark.parametrize("name", list(CASES))
def test_program_is_live(name):
    kn = B.panel_knobs(**CASES[name])
    a, b, first = B.compare(lambda k: kn, {26: 48.0, 66: 55.0}, 110, offs=(46, 100), vels={26: 100, 66: 60})
    assert first is None, first
    assert np.abs(b).max() > 0.001


def test_moving_knobs_then_another_material():
    A = B.panel_knobs(MAT="FIBER", MODE="MASS")
    S = B.panel_knobs(MAT="SKIN", GEST="STACC")

    def kn(k):
        if k < 70:
            x = list(A)
            x[8], x[21], x[23] = (k * 3) % 128, (k * 5) % 128, (k * 7) % 128
            return x
        return S
    a, b, first = B.compare(kn, {26: 48.0, 70: 60.0, 110: 50.0}, 140, offs=(60, 100))
    assert first is None, first
    assert (b[71 * 32:95 * 32] == 0).all()           # the clear after the faded block


def test_a_released_voice_rests_and_wakes():
    kn = B.panel_knobs(MAT="FIBER")
    a, b, first = B.compare(lambda k: kn, {26: 48.0, 900: 52.0}, 930, offs=(40,))
    assert first is None, first
    assert (b[850 * 32:900 * 32] == 0).all() and np.abs(b[900 * 32:]).max() > 0.005


def test_the_comparison_sees_a_wrong_program():
    """negative control: live with another knob than the frame's is caught"""
    kn = B.panel_knobs(MAT="FIBER")
    dsp = B.Dsp()
    v = L.SlotVoice(0)
    seen = None
    for k in range(40):
        f = B.Frame()
        words = B.knobs_words(kn)
        f.silt(0, words, 48.0, k == 26, 127, False)
        got = dsp.block(f, [0])[0]
        other = list(B.knobs_seen(words))
        other[8] += 1
        want = v.dsp_block(other, k == 26, 48.0, 127, False)
        if not np.array_equal(got.view(np.uint32), want.view(np.uint32)):
            seen = k
            break
    assert seen is not None


def test_the_words_fit():
    L_ = P.layout()
    assert L_.words_end <= L_.fl.scratch_end
    assert 4 * P.VOICE_WORDS <= P.STRIDE


def test_the_committed_tables_are_the_programs():
    from dnfw.silt import ddr
    assert ddr.tables_bytes() == P.tables_bytes()
