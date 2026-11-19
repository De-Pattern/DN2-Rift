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
    assert not M.is_choice("PATCH")              # v0.12: a wiring slot, 0..127 raw


def test_the_wire_tables_are_lives():
    """v0.12: the build's numpy-free copy (wire.json) is live's"""
    from dnfw.ligature import wire as W
    assert (W.NB, W.NSRC, W.NP, W.WSLOTS, W.WWORDS, W.WHDR, W.WMAGIC, W.WVERSION) == \
        (L.NB, L.NSRC, L.NP, L.WSLOTS, L.WWORDS, L.WHDR, L.WMAGIC, L.WVERSION)
    assert W.TYPES == L.TYPES and W.TYPE_NAMES == {t: L.TYPE_NAMES[t] for t in L.TYPES}
    assert W.factory() == [L.encode(*L.patch_rows(k)) for k in range(L.NP)]
    seed = L.seed_table()
    fac = W.factory()
    for k in range(L.WSLOTS):                     # lig.c's seed(): slot k = factory (k NP) >> 7
        assert seed[L.WHDR + L.WWORDS * k: L.WHDR + L.WWORDS * (k + 1)] == fac[min((k * L.NP) >> 7, L.NP - 1)]


def test_the_names_fit():
    for n in M.TYPE_SHORT.values():
        assert len(n) <= 4
    for a, b in M.TYPE_SETS.values():
        assert len(a) <= 4 and len(b) <= 4
    assert set(M.TYPE_SHORT) == set(L.TYPE_NAMES.values()) == set(M.TYPE_SETS) == set(M.TYPE_LONG)


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
