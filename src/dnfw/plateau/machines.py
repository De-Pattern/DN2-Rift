"""PLATEAU on the ColdFire: its machine type, its names, and the records its sixteen controls and its
BUS mask ride. No numpy: the build imports this.

Page 1, FX1 PLATE: PRED SIZE DCAY DIFF / DAMP BAND LCUT LEV.
Page 2, FX2 TANK: TLOW MSPD MDEP HOLD / TUND IGN DRV ERLY (HOLD and TUND OFF/ON).
A track is one machine or another, so they ride ORGAN's records (2..17, every one 0..127), as
DIGIDRUM's ride its first sixteen. The BUS mask (the tracks it hears: the REC BUS page's cells) rides
three more, six, six and four bits as knob values 0..63 (`mask_values`).
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 24                                  # RIFT v0.17 (23, THOLET's, is a gone type: it loads as FM Tone)
KIND = TYPE - 4
LONG, SHORT = "Plateau", "PLT"
LISTED = True

PAGES = {"FX1 PLATE": ("PRED", "SIZE", "DCAY", "DIFF", "DAMP", "BAND", "LCUT", "LEV"),
         "FX2 TANK": ("TLOW", "MSPD", "MDEP", "HOLD", "TUND", "IGN", "DRV", "ERLY")}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
_RIDES = list(OM.RIDES.values())
RIDES = dict(zip(CONTROLS, _RIDES[1:17]))
MASK_RIDES = (_RIDES[17], _RIDES[19], _RIDES[20])
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
MASK_SLOTS = tuple(FM.SLOTS[r][1] for r in MASK_RIDES)
CHOICES = {"HOLD": ("OFF", "ON"), "TUND": ("OFF", "ON")}
LABELS = {c: c for c in CONTROLS}
LONG_NAMES = {"PRED": "Pre-Delay", "SIZE": "Size", "DCAY": "Decay", "DIFF": "Diffusion",
              "DAMP": "Damping", "BAND": "Input High Cut", "LCUT": "Input Low Cut", "LEV": "Level",
              "TLOW": "Tank Low Cut", "MSPD": "Mod Speed", "MDEP": "Mod Depth", "HOLD": "Hold",
              "TUND": "Tuned", "IGN": "Input Gain", "DRV": "Drive", "ERLY": "Early"}
BOX = {"HOLD": "HOLD", "TUND": "TUND"}
OPT_DEFAULTS = {"HOLD": 0, "TUND": 0}
KNOB_DEFAULTS = {"PRED": 0, "SIZE": 76, "DCAY": 76, "DIFF": 127, "DAMP": 38, "BAND": 108, "LCUT": 6,
                 "LEV": 100, "TLOW": 6, "MSPD": 32, "MDEP": 38, "IGN": 64, "DRV": 0, "ERLY": 0}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ()
PAGE_TITLES = tuple(PAGES)
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
UNUSED_RECORDS = tuple(r for r in (FM.SLOTS[x][0] for x in FM.CONTROLS)
                       if r not in {SLOTS[c][0] for c in CONTROLS} | {FM.SLOTS[m][0] for m in MASK_RIDES}) \
    + tuple(OM.UNUSED_RECORDS)
FM_SLOT_FIRST, FM_SLOT_LAST, FM_OWNED = FM.FM_SLOT_FIRST, FM.FM_SLOT_LAST, FM.FM_OWNED

assert set(KNOB_DEFAULTS) | set(OPT_DEFAULTS) == set(CONTROLS)
assert all(FM.SLOTS[r][3] == 127 for r in list(RIDES.values()) + list(MASK_RIDES))
assert len(set(RIDES.values()) | set(MASK_RIDES)) == 19


def is_choice(c: str) -> bool:
    return c in CHOICES


def mask_values(mask: int) -> tuple[int, int, int]:
    """the three mask records' knob values (0..63 each) for a 16-bit track mask"""
    return mask & 63, mask >> 6 & 63, mask >> 12 & 15


def mask_of(values) -> int:
    a, b, c = values
    return (a & 63) | (b & 63) << 6 | (c & 15) << 12


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
    """the tables csrc/ reads (wr_gen.h), as DIGIDRUM's, prefix plt_; and the BUS mask's three
    records (plt_mask_rid, plt_mask_slot: six, six and four bits as knob values)"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    names: list[str] = []
    boxes: list[str] = []
    at = []
    for c in CONTROLS:
        at.append(len(names) if is_choice(c) else 0)
        if is_choice(c):
            names += list(CHOICES[c])
            boxes += list(CHOICES[c])
    if any(len(b) > 4 for b in boxes) or any(len(n) > 7 for n in names) or any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a PLATEAU name is too long for its box, the header or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO] or [0]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* PLATEAU (dnfw.plateau.machines; RIFT v0.17, the first FX machine) */",
        f"#define PLT_TYPE {TYPE}", f"#define PLT_KIND {KIND}", f"#define PLT_N {len(CONTROLS)}",
        f"#define PLT_PAGES {len(PAGES)}",
        f"static const unsigned short plt_rid[PLT_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char plt_slot[PLT_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char plt_lo[PLT_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char plt_top[PLT_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char plt_choices[PLT_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char plt_choice_at[PLT_N] = {{{arr(at)}}};",
        f"static const char plt_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char plt_choice_box[{len(boxes)}][5] = {{{', '.join(q + b + q for b in boxes)}}};",
        f"static const unsigned char plt_bipolar[PLT_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char plt_label[PLT_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short plt_default[PLT_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define PLT_NOLFO_N {len(nolfo)}",
        f"static const unsigned short plt_nolfo[PLT_NOLFO_N] = {{{arr(nolfo)}}};",
        f"static const unsigned short plt_mask_rid[3] = {{{arr(FM.SLOTS[r][0] for r in MASK_RIDES)}}};",
        f"static const unsigned char plt_mask_slot[3] = {{{arr(MASK_SLOTS)}}};",
        "",
    ])
