"""CONTOUR on the ColdFire: its machine type, its names, and the records its sixteen controls ride.
No numpy: the build imports this.

Page 1, SYN1 ORBIT: TUNE RATIO SIZX SIZY / CNTX CNTY ROT DRFT.
Page 2, SYN2 LAND: SURF MORPH WARP FOLD / FM FDBK GRIT LEV. A track is one machine or another, so
they ride FASCIA's records as ORGAN's first sixteen do (DIGIDRUM's way).
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 25                                  # after PLATEAU's 24
KIND = TYPE - 4
LONG, SHORT = "Contour", "CTR"
LISTED = True

PAGES = {"SYN1 ORBIT": ("TUNE", "RATIO", "SIZX", "SIZY", "CNTX", "CNTY", "ROT", "DRFT"),
         "SYN2 LAND": ("SURF", "MORPH", "WARP", "FOLD", "FM", "FDBK", "GRIT", "LEV")}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
RIDES = dict(zip(CONTROLS, list(OM.RIDES.values())[:len(CONTROLS)]))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
SURFACES = ("SINE", "FOLD", "CHEB", "FM", "RING", "EDGE", "CHAOS", "BITS")
CHOICES = {"SURF": SURFACES}
LABELS = {c: c for c in CONTROLS}
LONG_NAMES = {"TUNE": "Tune", "RATIO": "Y Ratio", "SIZX": "Size X", "SIZY": "Size Y", "CNTX": "Centre X",
              "CNTY": "Centre Y", "ROT": "Rotation", "DRFT": "Drift", "SURF": "Surface", "MORPH": "Morph",
              "WARP": "Warp", "FOLD": "Fold", "FM": "FM", "FDBK": "Feedback", "GRIT": "Grit", "LEV": "Level"}
BOX = {"SURF": "SURF"}
OPT_DEFAULTS = {"SURF": 0}
KNOB_DEFAULTS = {"TUNE": 64, "RATIO": 40, "SIZX": 90, "SIZY": 90, "CNTX": 64, "CNTY": 64, "ROT": 0, "DRFT": 0,
                 "MORPH": 0, "WARP": 0, "FOLD": 0, "FM": 0, "FDBK": 0, "GRIT": 0, "LEV": 100}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ("TUNE", "CNTX", "CNTY")
PAGE_TITLES = tuple(PAGES)
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
UNUSED_RECORDS = tuple(r for r in (FM.SLOTS[x][0] for x in FM.CONTROLS) if r not in {SLOTS[c][0] for c in CONTROLS}) \
    + tuple(OM.UNUSED_RECORDS)
FM_SLOT_FIRST, FM_SLOT_LAST, FM_OWNED = FM.FM_SLOT_FIRST, FM.FM_SLOT_LAST, FM.FM_OWNED

assert set(KNOB_DEFAULTS) | set(OPT_DEFAULTS) == set(CONTROLS)


def is_choice(c: str) -> bool:
    return c in CHOICES


def word_of(c: str, k: int) -> int:
    return FM.word_of(RIDES[c], k)


def option(c: str, k: int) -> int:
    n = len(CHOICES[c])
    return min((min(max(k, 0), 127) * n) >> 7, n - 1)


def rep_word(c: str, o: int) -> int:
    ks = [k for k in range(128) if option(c, k) == o]
    return word_of(c, (ks[0] + ks[-1]) // 2)


def default_words() -> dict[str, int]:
    out = {c: word_of(c, KNOB_DEFAULTS[c]) for c in KNOB_DEFAULTS}
    out.update({c: rep_word(c, o) for c, o in OPT_DEFAULTS.items()})
    return out


def c_header() -> str:
    """the tables csrc/ reads, as DIGIDRUM's, prefix ctr_"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    names: list[str] = []
    at = []
    for c in CONTROLS:
        at.append(len(names) if is_choice(c) else 0)
        if is_choice(c):
            names += list(CHOICES[c])
    if any(len(n) > 5 for n in names) or any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a CONTOUR name is too long for its box or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO] or [0]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* CONTOUR (dnfw.contour.machines) */",
        f"#define CTR_TYPE {TYPE}", f"#define CTR_KIND {KIND}", f"#define CTR_N {len(CONTROLS)}",
        f"#define CTR_PAGES {len(PAGES)}",
        f"static const unsigned short ctr_rid[CTR_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char ctr_slot[CTR_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char ctr_lo[CTR_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char ctr_top[CTR_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char ctr_choices[CTR_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char ctr_choice_at[CTR_N] = {{{arr(at)}}};",
        f"static const char ctr_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char ctr_choice_box[{len(names)}][5] = {{{', '.join(q + n[:4] + q for n in names)}}};",
        f"static const unsigned char ctr_bipolar[CTR_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char ctr_label[CTR_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short ctr_default[CTR_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define CTR_NOLFO_N {len(nolfo)}",
        f"static const unsigned short ctr_nolfo[CTR_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
