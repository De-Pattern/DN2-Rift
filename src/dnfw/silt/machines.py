"""SILT on the ColdFire: its machine type, its names, and the records its 32 controls ride (docs/silt-dsp.md).
The table the ColdFire's generated C header (dnfw.waverider.pages) and the DSP program (dnfw.silt.program,
through organ.live.RIDES) read. No numpy: the build imports this.

A track is one machine or another, so SILT rides FASCIA's records, in ORGAN's order (organ.live.RIDES):
pages 1-3 the 24 knobs, page 4 the 8 choices (MAT GEST MODE DIST LOOP SHAPE TUNE QUAL), latched by the
DSP at each trig. SHAPE, TUNE and QUAL ride FM Tone's 235..237 (no modulation); the rest of page 4 is an
LFO destination only as far as the trig's latch reads it.

The panel's labels use only the characters stock's own labels use (letters, digits, + - and space).
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 20                                  # after ORGAN's 19
KIND = TYPE - 4
LONG, SHORT = "Silt", "SLT"
LISTED = True

PAGES = {
    "SYN1 MATTER": ("PART", "TENS", "MASS", "COHE", "VISC", "GRAIN", "DENS", "BODY"),
    "SYN2 CONTACT": ("PRESS", "SPEED", "POS", "ROSIN", "SCRAP", "SNAP", "AIR", "INST"),
    "SYN3 STRUCTURE": ("SPREAD", "VOICES", "DRIFT", "VIBR", "GLISS", "FORM", "ROUGH", "MORPH"),
    "SYN4 CONFIG": ("MAT", "GEST", "MODE", "DIST", "LOOP", "SHAPE", "TUNE", "QUAL"),
}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
RIDES = dict(zip(CONTROLS, OM.RIDES.values()))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
CHOICES = {"MAT": ("FIBER", "SILT", "SKIN", "FLUID"),
           "GEST": ("BOW", "SCRAPE", "STACC", "TREMO", "SPICC", "LEGNO", "GLISS", "FRACT", "SWELL", "QUAKE"),
           "MODE": ("SOLO", "MASS", "MASS-8", "SWARM"),
           "DIST": ("NARROW", "WIDE", "BIMODAL", "ASYM"),
           "LOOP": ("OFF", "16TH", "8TH", "4TH", "FREE"),
           "SHAPE": ("SOFT", "LINEAR", "EXP", "CHAOTIC"),
           "TUNE": ("FREE", "SCALE", "MICRO", "HARM"),
           "QUAL": ("ECO", "NORMAL", "DEEP")}
LABELS = {"PART": "PART", "TENS": "TENS", "MASS": "MASS", "COHE": "COHE", "VISC": "VISC", "GRAIN": "GRAIN",
          "DENS": "DENS", "BODY": "BODY", "PRESS": "PRESS", "SPEED": "SPEED", "POS": "POS", "ROSIN": "ROSIN",
          "SCRAP": "SCRAP", "SNAP": "SNAP", "AIR": "AIR", "INST": "INST", "SPREAD": "SPRD", "VOICES": "VOICE",
          "DRIFT": "DRIFT", "VIBR": "VIBR", "GLISS": "GLISS", "FORM": "FORM", "ROUGH": "ROUGH", "MORPH": "MORPH",
          "MAT": "MAT", "GEST": "GEST", "MODE": "MODE", "DIST": "DIST", "LOOP": "LOOP", "SHAPE": "SHAPE",
          "TUNE": "TUNE", "QUAL": "QUAL"}
LONG_NAMES = {"PART": "Partials", "TENS": "Tension", "MASS": "Mass", "COHE": "Cohesion", "VISC": "Viscosity",
              "GRAIN": "Grain", "DENS": "Density", "BODY": "Body", "PRESS": "Pressure", "SPEED": "Speed",
              "POS": "Position", "ROSIN": "Rosin", "SCRAP": "Scrape", "SNAP": "Snap", "AIR": "Air",
              "INST": "Instability", "SPREAD": "Spread", "VOICES": "Voices", "DRIFT": "Drift", "VIBR": "Vibrato",
              "GLISS": "Glissando", "FORM": "Formant", "ROUGH": "Roughness", "MORPH": "Morph", "MAT": "Material",
              "GEST": "Gesture", "MODE": "Mode", "DIST": "Distribution", "LOOP": "Loop", "SHAPE": "Shape",
              "TUNE": "Tuning", "QUAL": "Quality"}
BOX = {"FIBER": "FIBR", "SILT": "SILT", "SKIN": "SKIN", "FLUID": "FLUD", "BOW": "BOW", "SCRAPE": "SCRP",
       "STACC": "STAC", "TREMO": "TREM", "SPICC": "SPIC", "LEGNO": "LEGN", "GLISS": "GLIS", "FRACT": "FRAC",
       "SWELL": "SWEL", "QUAKE": "QUAK", "SOLO": "SOLO", "MASS": "MASS", "MASS-8": "MS-8", "SWARM": "SWRM",
       "NARROW": "NARR", "WIDE": "WIDE", "BIMODAL": "BIMO", "ASYM": "ASYM", "OFF": "OFF", "16TH": "16TH",
       "8TH": "8TH", "4TH": "4TH", "FREE": "FREE", "SOFT": "SOFT", "LINEAR": "LIN", "EXP": "EXP",
       "CHAOTIC": "CHAO", "SCALE": "SCAL", "MICRO": "MICR", "HARM": "HARM", "ECO": "ECO", "NORMAL": "NORM",
       "DEEP": "DEEP"}
# the init sound: a gently bowed FIBER string, in tune (dnfw.silt.live.DEFAULTS, page 4 as options)
OPT_DEFAULTS = {"MAT": 0, "GEST": 0, "MODE": 0, "DIST": 0, "LOOP": 0, "SHAPE": 1, "TUNE": 0, "QUAL": 1}
KNOB_DEFAULTS = dict(PART=42, TENS=66, MASS=53, COHE=70, VISC=43, GRAIN=55, DENS=28, BODY=74,
                     PRESS=60, SPEED=64, POS=30, ROSIN=64, SCRAP=10, SNAP=40, AIR=10, INST=20,
                     SPREAD=0, VOICES=64, DRIFT=20, VIBR=30, GLISS=64, FORM=40, ROUGH=10, MORPH=0)
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ()
PAGE_TITLES = tuple(PAGES)
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
UNUSED_RECORDS = OM.UNUSED_RECORDS
FM_SLOT_FIRST, FM_SLOT_LAST, FM_OWNED = FM.FM_SLOT_FIRST, FM.FM_SLOT_LAST, FM.FM_OWNED

assert len(CONTROLS) == 32 and tuple(RIDES[c] for c in CONTROLS) == tuple(OM.RIDES.values())
assert set(OPT_DEFAULTS) == set(CHOICES) and set(KNOB_DEFAULTS) | set(CHOICES) == set(CONTROLS)


def is_choice(c: str) -> bool:
    return c in CHOICES


def option(c: str, k: int) -> int:
    n = len(CHOICES[c])
    return min((min(max(k, 0), 127) * n) >> 7, n - 1)


def word_of(c: str, k: int) -> int:
    return FM.word_of(RIDES[c], k)


def rep_word(c: str, o: int) -> int:
    ks = [k for k in range(128) if option(c, k) == o]
    return word_of(c, (ks[0] + ks[-1]) // 2)


def default_words() -> dict[str, int]:
    out = {c: word_of(c, KNOB_DEFAULTS[c]) for c in KNOB_DEFAULTS}
    out.update({c: rep_word(c, o) for c, o in OPT_DEFAULTS.items()})
    return out


def c_header() -> str:
    """the tables csrc/ reads (wr_gen.h), as ORGAN's, prefix slt_"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    names: list[str] = []
    boxes: list[str] = []
    at = []
    for c in CONTROLS:
        at.append(len(names) if is_choice(c) else 0)
        if is_choice(c):
            names += list(CHOICES[c])
            boxes += [BOX.get(n, n) for n in CHOICES[c]]
    if any(len(b) > 4 for b in boxes) or any(len(n) > 7 for n in names) or any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a SILT name is too long for its box, the header or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* SILT (dnfw.silt.machines) */",
        f"#define SLT_TYPE {TYPE}", f"#define SLT_KIND {KIND}", f"#define SLT_N {len(CONTROLS)}",
        f"#define SLT_PAGES {len(PAGES)}",
        f"static const unsigned short slt_rid[SLT_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char slt_slot[SLT_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char slt_lo[SLT_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char slt_top[SLT_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char slt_choices[SLT_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char slt_choice_at[SLT_N] = {{{arr(at)}}};",
        f"static const char slt_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char slt_choice_box[{len(boxes)}][5] = {{{', '.join(q + b + q for b in boxes)}}};",
        f"static const unsigned char slt_bipolar[SLT_N] = {{{arr(0 for _c in CONTROLS)}}};",
        f"static const char slt_label[SLT_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short slt_default[SLT_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define SLT_NOLFO_N {len(nolfo)}",
        f"static const unsigned short slt_nolfo[SLT_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
