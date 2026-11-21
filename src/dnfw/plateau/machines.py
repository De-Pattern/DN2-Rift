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

TYPE = 23                                  # THOLET's type in v0.15 and v0.16 (v0.17 removed it)
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
