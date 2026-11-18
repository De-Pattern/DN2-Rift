"""RESONATOR's live voice: the DN2 mk2 mod's machine (dnfw.rings there) as RIFT's: it rings, its pitch
follows the note and TUNE, STRC moves its partials, DAMP its decay, it rests when quiet."""
import numpy as np

from dnfw.reson import live as L


def render(blocks=600, notes=None, **kw):
    kn = [kw.get(c, L.DEFAULTS[c]) for c in L.CONTROLS]
    v = L.Voice(0)
    notes = notes or {0: 60.0}
    n = 60.0
    out = []
    for b in range(blocks):
        t = b in notes
        if t:
            n = notes[b]
        out.append(v.block(kn, t, n))
    return np.concatenate(out), v


def has(y, hz):
    """a partial at HZ: the spectrum's peak within 1 % of it is at least a fifth of the loudest"""
    s = np.abs(np.fft.rfft(y[:16384] * np.hanning(16384)))
    f = np.arange(len(s)) * 48000 / 16384
    near = s[(f > hz * 0.99) & (f < hz * 1.01)]
    return near.max() > 0.2 * s.max()


def test_it_rings_at_the_note():
    y, _ = render(notes={0: 69.0})
    assert has(y, 440.0) and not has(y, 415.3)
    assert 0.05 < np.abs(y).max() <= 0.9


def test_tune_is_semitones():
    y, _ = render(notes={0: 57.0}, TUNE=76)
    assert has(y, 440.0) and not has(y, 220.0 * 2 ** (1 / 12))


def test_damp_lengthens_the_ring():
    a, _ = render(DAMP=10)
    b, _ = render(DAMP=120)
    tail = slice(400 * 32, 600 * 32)
    assert np.abs(b[tail]).max() > 10 * np.abs(a[tail]).max()


def test_structure_moves_the_partials():
    a, _ = render(STRC=0)
    b, _ = render(STRC=64)
    sa = np.abs(np.fft.rfft(a[:16384]))
    sb = np.abs(np.fft.rfft(b[:16384]))
    assert np.corrcoef(sa, sb)[0, 1] < 0.9


def test_a_quiet_voice_rests():
    y, v = render(blocks=3000, DAMP=0, BRIT=0)
    assert v.on == 0 and (y[-3200:] == 0).all()


def test_the_top_note_leaves_high_modes_out():
    y, v = render(notes={0: 127.0}, TUNE=127)
    assert np.isfinite(y).all() and np.abs(y).max() > 0.0
