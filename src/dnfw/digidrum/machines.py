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
