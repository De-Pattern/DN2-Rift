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
    assert all(FM.SLOTS[OM.RIDES[c]][3] == 127 for c in OM.CONTROLS if c != "STOP")
    assert [OM.option("STOP", OM.knob("STOP", OM.rep_word("STOP", o))) for o in range(5)] == list(range(5))


def test_defaults_are_ravels():
    w = OM.default_words()
    assert OM.option("STOP", OM.knob("STOP", w["STOP"])) == 1               # NACHTHORN
    assert {c: OM.knob(c, w[c]) for c in OM.CONTROLS if c != "STOP"} == \
        {c: v for c, v in OM.DEFAULTS.items() if c != "STOP"}


def test_the_header_and_the_lists():
    h = pages.c_header()
    assert "#define ORG_TYPE 19" in h and "wr_mach_org" in h and "org_default" in h
    assert OM.TYPE in coldfire.NEW_TYPES and coldfire.MACHINE_NAMES[OM.TYPE] == ("Organ", "ORG")
    lst = coldfire.LIST_NEW
    assert lst.index(OM.TYPE) == lst.index(FM.TYPE) + 1
    named = pages.org_named()
    assert all(named[OM.SLOTS[c][0]] == (OM.LONG_NAMES[c], OM.LABELS[c]) for c in OM.CONTROLS)
    assert all(named[r] == (pages.UNUSED_LONG, pages.UNUSED_SHORT) for r in OM.UNUSED_RECORDS)
