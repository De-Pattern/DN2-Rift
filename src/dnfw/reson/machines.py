"""RESONATOR on the ColdFire: its machine type, its names, and the records its eight controls ride. The
table the ColdFire's generated C header (dnfw.waverider.pages) and the DSP program (dnfw.reson.program)
read. No numpy: the build imports this.

A track is one machine or another, so RESONATOR rides FASCIA's records, ORGAN's first eight
(organ.live.RIDES): one page, TUNE LEV STRC BRIT / DAMP POS EXCT HIT, as the DN2 mk2 mod's v0.21.
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 22                                  # after LIGATURE's 21
KIND = TYPE - 4
LONG, SHORT = "Resonator", "RES"
LISTED = True

PAGES = {"SYN1 RESONATOR": ("TUNE", "LEV", "STRC", "BRIT", "DAMP", "POS", "EXCT", "HIT")}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
RIDES = dict(zip(CONTROLS, list(OM.RIDES.values())[:len(CONTROLS)]))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
CHOICES: dict[str, tuple[str, ...]] = {}
LABELS = {c: c for c in CONTROLS}
LONG_NAMES = {"TUNE": "Tune", "LEV": "Level", "STRC": "Structure", "BRIT": "Brightness", "DAMP": "Damping",
              "POS": "Position", "EXCT": "Exciter", "HIT": "Hit"}
BOX: dict[str, str] = {}
OPT_DEFAULTS: dict[str, int] = {}
KNOB_DEFAULTS = {"TUNE": 64, "LEV": 100, "STRC": 0, "BRIT": 127, "DAMP": 110, "POS": 64, "EXCT": 64, "HIT": 100}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ("TUNE",)
PAGE_TITLES = tuple(PAGES)
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
# FASCIA's other 24 records (the controls RESONATOR does not ride), then ORGAN's unused: named "-", no LFO
UNUSED_RECORDS = tuple(r for r in (FM.SLOTS[x][0] for x in FM.CONTROLS) if r not in {SLOTS[c][0] for c in CONTROLS}) \
    + tuple(OM.UNUSED_RECORDS)
FM_SLOT_FIRST, FM_SLOT_LAST, FM_OWNED = FM.FM_SLOT_FIRST, FM.FM_SLOT_LAST, FM.FM_OWNED

assert set(KNOB_DEFAULTS) == set(CONTROLS)


def is_choice(c: str) -> bool:
    return c in CHOICES


def word_of(c: str, k: int) -> int:
    return FM.word_of(RIDES[c], k)


def default_words() -> dict[str, int]:
    return {c: word_of(c, KNOB_DEFAULTS[c]) for c in KNOB_DEFAULTS}


def c_header() -> str:
    """the tables csrc/ reads (wr_gen.h), as LIGATURE's, prefix res_"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    if any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a RESONATOR label is too long")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO] or [0]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* RESONATOR (dnfw.reson.machines) */",
        f"#define RES_TYPE {TYPE}", f"#define RES_KIND {KIND}", f"#define RES_N {len(CONTROLS)}",
        f"#define RES_PAGES {len(PAGES)}",
        f"static const unsigned short res_rid[RES_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char res_slot[RES_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char res_lo[RES_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char res_top[RES_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char res_choices[RES_N] = {{{arr(0 for _c in CONTROLS)}}};",
        f"static const unsigned char res_choice_at[RES_N] = {{{arr(0 for _c in CONTROLS)}}};",
        f"static const char res_choice_name[1][8] = {{{q}{q}}};",
        f"static const char res_choice_box[1][5] = {{{q}{q}}};",
        f"static const unsigned char res_bipolar[RES_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char res_label[RES_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short res_default[RES_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define RES_NOLFO_N {len(nolfo)}",
        f"static const unsigned short res_nolfo[RES_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
