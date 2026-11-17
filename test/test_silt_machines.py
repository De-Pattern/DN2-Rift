"""SILT on the ColdFire (dnfw.silt.machines) agrees with the DSP's reading of it (dnfw.silt.live/program)."""
from dnfw.fascia import machines as FM
from dnfw.organ import live as OL
from dnfw.silt import live as L
from dnfw.silt import machines as M


def test_controls_and_rides_are_the_dsps():
    assert M.CONTROLS == L.CONTROLS
    assert tuple(M.RIDES[c] for c in M.CONTROLS) == OL.RIDES
    assert len({M.SLOTS[c][0] for c in M.CONTROLS}) == 32


def test_choices_are_the_dsps_and_its_option_reading():
    for c, names in M.CHOICES.items():
        assert len(names) == len(L.CHOICES[c])
        for k in range(128):
            assert M.option(c, k) == L.knob_option(k, len(names))


def test_defaults_read_back_as_the_init_sound():
    words = M.default_words()
    for j, c in enumerate(M.CONTROLS):
        top = FM.SLOTS[M.RIDES[c]][3]
        k = OL.knob_of(words[c], top)
        if M.is_choice(c):
            assert L.knob_option(k, len(M.CHOICES[c])) == L.DEFAULTS[c], c
        else:
            assert abs(k - L.DEFAULTS[c]) <= 1, c


def test_the_header_fits():
    hdr = M.c_header()
    assert "#define SLT_TYPE 20" in hdr and "#define SLT_N 32" in hdr and "#define SLT_PAGES 4" in hdr
    assert M.NO_LFO == ("SHAPE", "TUNE", "QUAL")
