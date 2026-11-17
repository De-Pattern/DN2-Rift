"""ORGAN's ColdFire table (dnfw.organ.machines) against its DSP program's (dnfw.organ.live) and the
generated header: the same records, in the same order, every name fitting its place."""
from dnfw.fascia import machines as FM
from dnfw.organ import live as LV
from dnfw.organ import machines as OM
from dnfw.waverider import coldfire, pages


def test_the_rides_are_the_dsps():
    assert OM.CONTROLS == LV.CONTROLS
    assert tuple(OM.RIDES[c] for c in OM.CONTROLS) == LV.RIDES
    assert {OM.SLOTS[c][0] for c in OM.CONTROLS} <= {r for r, _s, _l, _t in FM.SLOTS.values()}


def test_stop_is_a_choice_on_a_choice_record_and_the_rest_continuous():
    assert OM.is_choice("STOP") and FM.SLOTS[OM.RIDES["STOP"]][3] in (100, 120)
    assert not OM.is_choice("MTUN") and FM.SLOTS[OM.RIDES["MTUN"]][3] in (100, 120)   # v0.6: a knob on PHRM's record
    # pages 1 and 2 on 0..127 records; v0.5's pages 3 and 4 also on PD1, PD2, OFS1, OFS2 (0..100),
    # read as 0..127 knobs (live.knob_of, fmt.c fsc_kn)
    assert all(FM.SLOTS[OM.RIDES[c]][3] == 127 for c in OM.CONTROLS[:16] if c != "STOP")
    assert all(FM.SLOTS[OM.RIDES[c]][3] in (100, 127) for c in OM.CONTROLS[16:] if c != "MTUN")
    assert [OM.option("STOP", OM.knob("STOP", OM.rep_word("STOP", o))) for o in range(5)] == list(range(5))


def test_v04_sounds_read_as_pages_3_and_4_off():
    """a v0.4 ORGAN sound holds stock's record defaults on pages 3 and 4's records: the DSP reads
    them as 0 (live.LEGACY), the ColdFire knows the same words, and v0.5's own defaults are not them"""
    assert OM.LEGACY_WORDS == LV.LEGACY_WORDS and OM.LEGACY_FIRST == 16
    assert LV.LEGACY_TOPS == tuple(FM.SLOTS[r][3] for r in LV.RIDES[16:])
    assert tuple(OM.knob(c, w) for c, w in zip(OM.CONTROLS[16:], OM.LEGACY_WORDS)) == LV.LEGACY
    dw = OM.default_words()
    assert tuple(dw[c] for c in OM.CONTROLS[16:]) != OM.LEGACY_WORDS
    e = LV.eff_of([OM.knob(c, dw[c]) for c in OM.CONTROLS[:16]] + list(LV.LEGACY))
    assert all(x == 0 for x in e[16:])
    h = pages.c_header()
    assert "#define ORG_LEGACY_FIRST 16" in h and "org_legacy[ORG_N - ORG_LEGACY_FIRST]" in h


def test_defaults_are_ravels():
    w = OM.default_words()
    assert OM.option("STOP", OM.knob("STOP", w["STOP"])) == 1               # NACHTHORN
    assert OM.knob("MTUN", w["MTUN"]) == 0                                  # v0.6: the mixture in tune
    assert {c: OM.knob(c, w[c]) for c in OM.CONTROLS if c not in OM.CHOICES} == \
        {c: v for c, v in OM.DEFAULTS.items() if c not in OM.CHOICES}


def test_the_header_and_the_lists():
    h = pages.c_header()
    assert "#define ORG_TYPE 19" in h and "wr_mach_org" in h and "org_default" in h
    assert OM.TYPE in coldfire.NEW_TYPES and coldfire.MACHINE_NAMES[OM.TYPE] == ("Organ", "ORG")
    lst = coldfire.LIST_NEW
    assert lst.index(OM.TYPE) == lst.index(FM.TYPE) + 1
    named = pages.org_named()
    assert all(named[OM.SLOTS[c][0]] == (OM.LONG_NAMES[c], OM.LABELS[c]) for c in OM.CONTROLS)
    assert all(named[r] == (pages.UNUSED_LONG, pages.UNUSED_SHORT) for r in OM.UNUSED_RECORDS)
