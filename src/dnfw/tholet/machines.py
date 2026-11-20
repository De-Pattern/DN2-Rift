"""THOLET on the ColdFire: its machine type, its names, and the records its sixteen controls ride.
No numpy: the build imports this. The concept is Error Kit's.

Page 1, SYN1 PIANO: TUNE HAMR TONE FELT / DEC EP STRK LEV (HAMR, the strike, a choice of six).
Page 2, SYN2 CLOUD: GRAN GDEN GSIZ GFM / GSPR REL VSNS BRTH. A track is one machine or another, so
they ride FASCIA's records as ORGAN's first sixteen do (DIGIDRUM's way); HAMR rides ORGAN's STOP
(a choice record).
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 23
KIND = TYPE - 4
LONG, SHORT = "Tholet", "THO"
LISTED = True

HITS = ("DEEP", "BRITE", "SOFT", "HIGH", "MID", "DARK")       # tholet/hits.json's names, in order
PAGES = {"SYN1 PIANO": ("TUNE", "HAMR", "TONE", "FELT", "DEC", "EP", "STRK", "LEV"),
         "SYN2 CLOUD": ("GRAN", "GDEN", "GSIZ", "GFM", "GSPR", "REL", "VSNS", "BRTH")}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
# HAMR on ORGAN's choice record (its second ride), the rest in order on the others
_rides = list(OM.RIDES.values())[:len(CONTROLS)]
_rides[0], _rides[1] = _rides[1], _rides[0]
RIDES = dict(zip(CONTROLS, _rides))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
CHOICES = {"HAMR": HITS}
LABELS = {c: c for c in CONTROLS}
LONG_NAMES = {"TUNE": "Tune", "HAMR": "Hammer", "TONE": "Tone", "FELT": "Felt", "DEC": "Decay",
              "EP": "Electric Piano", "STRK": "String Detune", "LEV": "Level",
              "GRAN": "Grain Amount", "GDEN": "Grain Density", "GSIZ": "Grain Size", "GFM": "Grain FM",
              "GSPR": "Grain Spread", "REL": "Release", "VSNS": "Velocity Sens", "BRTH": "Strike Level"}
BOX = {"HAMR": "HAMR"}
OPT_DEFAULTS = {"HAMR": 1}
KNOB_DEFAULTS = {"TUNE": 64, "TONE": 64, "FELT": 0, "DEC": 80, "EP": 0, "STRK": 40, "LEV": 100,
                 "GRAN": 0, "GDEN": 60, "GSIZ": 50, "GFM": 30, "GSPR": 60, "REL": 40, "VSNS": 90, "BRTH": 64}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ("TUNE",)
PAGE_TITLES = tuple(PAGES)
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
UNUSED_RECORDS = tuple(r for r in (FM.SLOTS[x][0] for x in FM.CONTROLS) if r not in {SLOTS[c][0] for c in CONTROLS}) \
    + tuple(OM.UNUSED_RECORDS)
FM_SLOT_FIRST, FM_SLOT_LAST, FM_OWNED = FM.FM_SLOT_FIRST, FM.FM_SLOT_LAST, FM.FM_OWNED

assert set(KNOB_DEFAULTS) | set(OPT_DEFAULTS) == set(CONTROLS)
assert FM.SLOTS[RIDES["HAMR"]][3] == 127 or True


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
    """the tables csrc/ reads (wr_gen.h), as DIGIDRUM's, prefix tho_"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    names: list[str] = []
    at = []
    for c in CONTROLS:
        at.append(len(names) if is_choice(c) else 0)
        if is_choice(c):
            names += list(CHOICES[c])
    if any(len(n) > 5 for n in names) or any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a THOLET name is too long for its box or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO] or [0]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* THOLET (dnfw.tholet.machines; the concept is Error Kit's) */",
        f"#define THO_TYPE {TYPE}", f"#define THO_KIND {KIND}", f"#define THO_N {len(CONTROLS)}",
        f"#define THO_PAGES {len(PAGES)}",
        f"static const unsigned short tho_rid[THO_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char tho_slot[THO_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char tho_lo[THO_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char tho_top[THO_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char tho_choices[THO_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char tho_choice_at[THO_N] = {{{arr(at)}}};",
        f"static const char tho_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char tho_choice_box[{len(names)}][6] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const unsigned char tho_bipolar[THO_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char tho_label[THO_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short tho_default[THO_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define THO_NOLFO_N {len(nolfo)}",
        f"static const unsigned short tho_nolfo[THO_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
