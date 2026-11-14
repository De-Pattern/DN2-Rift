"""The insert effects' reference models (src/dnfw/fx, docs/fx-platform.md): what each must do
whatever the owner's ear decides about its sound."""
import numpy as np
import pytest

from dnfw.fx import chrono as C
from dnfw.fx import reson as R
from dnfw.fx import resonator as RS
from dnfw.fx import warp as W

SR = 48000
T = np.arange(SR) / SR
SINE = 0.3 * np.sin(2 * np.pi * 440 * T)


def _drums(n=SR, seed=1):
    rng = np.random.default_rng(seed)
    x = 0.2 * ((T[:n] * 110) % 1 * 2 - 1)
    for k in range(0, n, n // 4):
        m = min(800, n - k)
        x[k:k + m] += rng.standard_normal(m) * np.exp(-np.arange(m) / 150)
    return x


def _f0(y, lo=50.0, hi=2000.0):
    """The fundamental by autocorrelation: the lag of the highest peak past the first dip."""
    y = y - np.mean(y)
    r = np.correlate(y, y, "full")[len(y) - 1:]
    a, b = int(SR / hi), int(SR / lo)
    k = a + int(np.argmax(r[a:b]))
    return SR / k


def _peak_hz(y):
    Y = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    return np.argmax(Y) * SR / len(y)


@pytest.mark.parametrize("prof", R.PROFILE_NAMES)
def test_every_reson_profile_is_finite_and_bounded(prof):
    x = _drums()
    y = R.Reson().process(x, R.params(prof), note_on=[0, SR // 2])
    assert np.all(np.isfinite(y))
    assert np.max(np.abs(y)) < 8 * np.max(np.abs(x))


def test_reson_is_deterministic_and_off_is_dry():
    x = _drums()
    a = R.Reson().process(x, R.params("DUST"))
    b = R.Reson().process(x, R.params("DUST"))
    assert np.array_equal(a, b)
    assert np.array_equal(R.Reson().process(x, R.params(MODE="OFF")), x)
    assert np.allclose(R.Reson().process(x, R.params("GLASS", MIX=0, DROP=0)), x)


def test_reson_ping_rings_its_bands_after_the_input_stops():
    x = np.zeros(SR)
    x[:200] = _drums()[:200]
    y = R.Reson().process(x, R.params("DUST", DUST=0), note_on=[0])
    late = y[SR // 4:SR // 4 + 4800]
    assert np.sqrt(np.mean(late ** 2)) > 1e-4          # still ringing 250 ms after a 4 ms burst


def test_reson_profiles_turn_the_page_knobs():
    p = R.params("RADIO", RESO=10, WDTH=100, SHFT=70, LIQ=5, DUST=3, DROP=2, MODE="PING")
    assert (p[R.IX["MODE"]], p[R.IX["RESO"]], p[R.IX["WIDTH"]], p[R.IX["SHIFT"]]) == (3, 10, 100, 70)
    assert (p[R.IX["LIQ"]], p[R.IX["DUST"]], p[R.IX["DROP"]]) == (5, 3, 2)
    assert p[R.IX["G2"]] == 105                          # RADIO's own band gains stay


def test_resonator_rings_at_its_root_and_mix_zero_is_dry():
    x = np.zeros(SR)
    x[:64] = np.random.default_rng(3).standard_normal(64)
    y = RS.Resonator().process(x, RS.params(ROOT=57, CHRD="ROOT", KEYT=0, FDBK=125, MIX=127, DTUN=0))
    assert abs(_f0(y[2000:14000]) - 220.0) < 2.0           # A3
    assert np.array_equal(RS.Resonator().process(SINE, RS.params(MIX=0)), SINE)


@pytest.mark.parametrize("chord", RS.CHORD_NAMES)
def test_every_resonator_chord_is_finite_and_bounded(chord):
    y = RS.Resonator().process(_drums(), RS.params(CHRD=chord, FDBK=127, ENVM=127, DRIV=127))
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) < 10


def test_warp_moves_a_sine_by_shft_and_suppresses_the_other_sideband():
    y = W.Warp().process(SINE, W.params(SHFT=127, RANG=0, MIX=127))[SR // 4:]
    assert abs(_peak_hz(y) - 490.0) < 2.0                    # +50 Hz
    Y = np.abs(np.fft.rfft(y * np.hanning(len(y))))
    lsb = Y[int(390 * len(y) / SR)]
    assert 20 * np.log10(lsb / Y.max()) < -20
    y = W.Warp().process(SINE, W.params(SHFT=127, RANG=0, SBND=127, MIX=127))[SR // 4:]
    assert abs(_peak_hz(y) - 390.0) < 2.0                    # SBND 127: the lower sideband


def test_warp_feedback_stays_bounded():
    y = W.Warp().process(_drums(), W.params(FDBK=127, SBND=64, DEP=127, SPD=127, MIX=127))
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) < 4


@pytest.mark.parametrize("tune,semis", [(96, 12), (32, -12), (127, 24)])
def test_chrono_shifts_by_tune_within_a_grain_rate(tune, semis):
    p = C.params(TUNE=tune, WIN=80, JITR=0, MIX=127)
    y = C.Chrono().process(SINE, p)[SR // 4:]
    grain_hz = SR / int((0.005 + 0.115 * (80 / 127) ** 1.5) * SR)
    assert abs(_peak_hz(y) - 440 * 2 ** (semis / 12)) <= grain_hz


def test_chrono_feedback_is_bounded_and_mix_zero_is_dry():
    y = C.Chrono().process(_drums(), C.params(FDBK=127, TUNE=127, WIN=127, MIX=127))
    assert np.all(np.isfinite(y)) and np.max(np.abs(y)) < 6
    assert np.array_equal(C.Chrono().process(SINE, C.params(MIX=0)), SINE)
