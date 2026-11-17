"""LIGATURE on the ColdFire (dnfw.ligature.machines) agrees with the DSP's reading of it (dnfw.ligature.live/program)."""
from dnfw.fascia import machines as FM
from dnfw.organ import live as OL
from dnfw.ligature import live as L
from dnfw.ligature import machines as M


def test_controls_and_rides_are_the_dsps():
    assert M.CONTROLS == L.CONTROLS
    assert tuple(M.RIDES[c] for c in M.CONTROLS) == OL.RIDES
    assert len({M.SLOTS[c][0] for c in M.CONTROLS}) == 32


def test_patch_names_and_reading_are_the_dsps():
    assert M.PATCH_NAMES == tuple(n for n, *_r in L.PATCHES)
    for kk in range(128):
        assert M.option("PATCH", kk) == L.patch_of(kk)


def test_defaults_read_back_as_the_init_sound():
    words = M.default_words()
    for c in M.CONTROLS:
        top = FM.SLOTS[M.RIDES[c]][3]
        kk = OL.knob_of(words[c], top)
        if M.is_choice(c):
            assert L.patch_of(kk) == L.DEFAULTS[c], c
        else:
            assert kk == L.DEFAULTS[c], c          # exact: 64 is each setting's patch value


def test_the_header_fits():
    hdr = M.c_header()
    assert "#define LIG_TYPE 21" in hdr and "#define LIG_N 32" in hdr and "#define LIG_PAGES 4" in hdr
    assert M.NO_LFO == ("S11B", "S12A", "S12B")
