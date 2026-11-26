"""DIGIDRUM on the ColdFire: its machine type, its names, and the records its sixteen controls ride.
No numpy: the build imports this.

Page 1, SYN1 DRUM: TYPE TUNE PNCH DEC, then the type's own four (O1..O4, labelled by the type).
Page 2, SYN2 TONE: OVER EQF EQG AMD / AMF FLTF FLTW LEV. A track is one machine or another, so they
ride FASCIA's records as ORGAN's first sixteen do; TYPE rides ORGAN's STOP (a choice record).
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 22                                  # RESONATOR's type until v0.9, which removed it
KIND = TYPE - 4
LONG, SHORT = "Digidrum", "DGD"
LISTED = True

TYPES = ("BD MODERN", "SD BASIC", "SD VINTAGE", "CP VINTAGE", "CY ALLOY", "PC CARBON")
TYPE_BOX = ("BD.M", "SD.B", "SD.V", "CP.V", "CY.A", "PC.C")
OWN = {"BD MODERN": ("SWEP", "SMOD", "TMOD", "MENV"),
       "SD BASIC": ("SWEP", "INHM", "MDFB", "MENV"),
       "SD VINTAGE": ("SWEP", "INHM", "FCMP", "MENV"),
       "CP VINTAGE": ("SPCR", "BAL", "BODY", "BENV"),
       "CY ALLOY": ("SHIM", "RADIO", "MOD", "MENV"),
       "PC CARBON": ("SWEP", "INHM", "MOD", "MENV")}
PAGES = {"SYN1 DRUM": ("TYPE", "TUNE", "PNCH", "DEC", "O1", "O2", "O3", "O4"),
         "SYN2 TONE": ("OVER", "EQF", "EQG", "AMD", "AMF", "FLTF", "FLTW", "LEV")}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
RIDES = dict(zip(CONTROLS, list(OM.RIDES.values())[:len(CONTROLS)]))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
CHOICES = {"TYPE": TYPES}
LABELS = {c: c for c in CONTROLS}          # O1..O4 are drawn with the type's own names (OWN)
LONG_NAMES = {"TYPE": "Drum Type", "TUNE": "Tune", "PNCH": "Punch", "DEC": "Decay",
              "O1": "Type Control 1", "O2": "Type Control 2", "O3": "Type Control 3", "O4": "Type Control 4",
              "OVER": "Overdrive", "EQF": "EQ Frequency", "EQG": "EQ Gain", "AMD": "AM Depth", "AMF": "AM Rate",
              "FLTF": "Filter Base", "FLTW": "Filter Width", "LEV": "Level"}
OWN_LONG = {"SWEP": "Sweep", "SMOD": "Square Mod", "TMOD": "Triangle Mod", "MENV": "Mod Envelope",
            "INHM": "Inharmonic", "MDFB": "Mod Feedback", "FCMP": "Freq Compress", "SPCR": "Spacing",
            "BAL": "Balance", "BODY": "Body", "BENV": "Body Envelope", "SHIM": "Shimmer", "RADIO": "Radio",
            "MOD": "Modulation"}
BOX = {"TYPE": "TYPE"}
OPT_DEFAULTS = {"TYPE": 0}
KNOB_DEFAULTS = {"TUNE": 64, "PNCH": 30, "DEC": 64, "O1": 64, "O2": 64, "O3": 64, "O4": 64,
                 "OVER": 0, "EQF": 64, "EQG": 64, "AMD": 0, "AMF": 64, "FLTF": 0, "FLTW": 127, "LEV": 100}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ("TUNE", "EQG")
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
    """the tables csrc/ reads (wr_gen.h), as SILT's, prefix dgd_; and the type's own four labels
    (dgd_own: 6 types x 4, what O1..O4 are drawn as)"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    names: list[str] = []
    boxes: list[str] = []
    at = []
    for c in CONTROLS:
        at.append(len(names) if is_choice(c) else 0)
        if is_choice(c):
            names += list(CHOICES[c])
            boxes += list(TYPE_BOX)
    if any(len(b) > 4 for b in boxes) or any(len(n) > 10 for n in names) or any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a DIGIDRUM name is too long for its box, the header or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO] or [0]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* DIGIDRUM (dnfw.digidrum.machines) */",
        f"#define DGD_TYPE {TYPE}", f"#define DGD_KIND {KIND}", f"#define DGD_N {len(CONTROLS)}",
        f"#define DGD_PAGES {len(PAGES)}",
        f"static const unsigned short dgd_rid[DGD_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char dgd_slot[DGD_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char dgd_lo[DGD_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char dgd_top[DGD_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char dgd_choices[DGD_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char dgd_choice_at[DGD_N] = {{{arr(at)}}};",
        f"static const char dgd_choice_name[{len(names)}][8] = {{{', '.join(q + n.replace('MODERN', 'MOD').replace('VINTAGE', 'VIN').replace('BASIC', 'BAS').replace('ALLOY', 'ALY').replace('CARBON', 'CRB') + q for n in names)}}};",
        f"static const char dgd_choice_box[{len(boxes)}][5] = {{{', '.join(q + b + q for b in boxes)}}};",
        f"static const unsigned char dgd_bipolar[DGD_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char dgd_label[DGD_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const char dgd_own[{len(TYPES)}][4][6] = {{{', '.join('{' + ', '.join(q + o + q for o in OWN[t]) + '}' for t in TYPES)}}};",
        # RIFT v0.28 (franny: O1..O4 read "Type Control 1".. in the header while turned): their long names by TYPE
        f"static const char *const dgd_own_long[{len(TYPES)}][4] = {{{', '.join('{' + ', '.join(q + OWN_LONG[o] + q for o in OWN[t]) + '}' for t in TYPES)}}};",
        f"static const unsigned short dgd_default[DGD_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define DGD_NOLFO_N {len(nolfo)}",
        f"static const unsigned short dgd_nolfo[DGD_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
