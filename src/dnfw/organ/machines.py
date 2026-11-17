"""ORGAN on the ColdFire: its machine type, its names, and the records its 16 controls ride
(docs/organ.md). The one table the ColdFire's generated C header (dnfw.waverider.pages) and the
DSP program (dnfw.organ.program, through live.RIDES) read. No numpy: the build imports this.

A track is one machine or the other, so ORGAN rides FASCIA's records: a FASCIA sound's records
(WaveTone's and FM Tone's on slots 50..64) are an ORGAN sound's too. STOP rides WAV1's 0..120 choice
record (FASCIA's TYPA); the fifteen others 0..127 records, those with a stock CC first. Every one of
them is an LFO destination (none of FM Tone's 235..237, whose modulation mask is 0).

The panel's labels use only the characters stock's own labels use (letters, digits, + - and space):
the ranks by their foot or their name (NAZ the Nazard, 2 2/3 ft; TIER the Tierce, 1 3/5 ft).
"""

from __future__ import annotations

from ..fascia import machines as FM

TYPE = 19                                  # after FASCIA's 18: a new type (never PERC's or the MnM's freed ones)
KIND = TYPE - 4                            # is_wr's answer (dnfw.waverider.pages)
LONG, SHORT = "Organ", "ORG"               # MACHINE SEL's names
LISTED = True

STOPS = ("FLUTE", "NACHTHN", "PRINCPL", "GAMBA", "TRUMPET")   # Ravel's FLUTE NACHTHORN PRINCIPAL GAMBA TRUMPET
PAGES = {
    "SYN1 RANKS": ("STOP", "R16", "R8", "R4", "R223", "R2", "R135", "R1"),
    "SYN2 PIPES": ("CHIFF", "SPEECH", "SPREAD", "AIR", "WIND", "TREM", "TRATE", "CELESTE"),
    # v0.5 (owner, 2026-11-16): attack and tone, then the breath (his flute clip); both pages at 0
    # leave v0.4's organ as it was
    "SYN3 ATTACK": ("PERC", "PDEC", "MTUN", "KCLK", "MCHR", "MIXT", "ROTR", "RSPD"),
    "SYN4 BREATH": ("BRTH", "TURB", "BREK", "BDEP", "PRES", "BLOM", "EDGE", "PVEL"),
}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
# the record each control rides: FASCIA's control of that name (dnfw.organ.live.RIDES, the DSP's)
RIDES = dict(zip(CONTROLS, ("TYPA", "HARD", "TUNE", "DAMP", "DEC", "MORPH", "FORM", "SHIFT",
                            "LPG", "CHAR", "CLIK", "WATR", "FOLD", "SIDE", "DUST", "TZFM",
                            "BEND", "MIX", "TYPB", "GEOM", "MATL", "POS", "COUP", "RING",
                            "BUZZ", "BODA", "BODB", "CTYP", "XMOD", "ATK", "FDBK", "VARY")))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
CHOICES = {"STOP": STOPS}                  # v0.6: PHRM (2ND/3RD) is MTUN, a knob
LABELS = {"STOP": "STOP", "R16": "16FT", "R8": "8FT", "R4": "4FT", "R223": "NAZ", "R2": "2FT",
          "R135": "TIER", "R1": "1FT", "CHIFF": "CHIFF", "SPEECH": "SPCH", "SPREAD": "SPRD",
          "AIR": "AIR", "WIND": "WIND", "TREM": "TREM", "TRATE": "RATE", "CELESTE": "CELST",
          "PERC": "PERC", "PDEC": "PDEC", "MTUN": "MTUN", "KCLK": "KCLK", "MCHR": "MCHR", "MIXT": "MIXT",
          "ROTR": "ROTR", "RSPD": "RSPD", "BRTH": "BRTH", "TURB": "TURB", "BREK": "BREK", "BDEP": "BDEP",
          "PRES": "PRES", "BLOM": "BLOM", "EDGE": "EDGE", "PVEL": "PVEL"}
LONG_NAMES = {"STOP": "Stop", "R16": "Rank 16 Foot", "R8": "Rank 8 Foot", "R4": "Rank 4 Foot",
              "R223": "Nazard", "R2": "Rank 2 Foot", "R135": "Tierce", "R1": "Rank 1 Foot",
              "CHIFF": "Chiff", "SPEECH": "Speech", "SPREAD": "Spread", "AIR": "Air", "WIND": "Wind",
              "TREM": "Tremulant", "TRATE": "Tremulant Rate", "CELESTE": "Celeste",
              "PERC": "Percussion", "PDEC": "Percussion Decay", "MTUN": "Mixture Tune", "KCLK": "Key Click",
              "MCHR": "Mixture Character", "MIXT": "Mixture", "ROTR": "Rotor", "RSPD": "Rotor Speed",
              "BRTH": "Breath", "TURB": "Turbulence", "BREK": "Break", "BDEP": "Break Depth",
              "PRES": "Pressure", "BLOM": "Bloom", "EDGE": "Edge", "PVEL": "Pressure Velocity"}
BOX = {"FLUTE": "FLUT", "NACHTHN": "NACH", "PRINCPL": "PRIN", "GAMBA": "GAMB", "TRUMPET": "TRMP"}
# Ravel's defaults (docs/organ.md): STOP NACHTHORN; knobs 0..127 (STOP: a knob in its option's span)
DEFAULTS = {"STOP": 38, "R16": 0, "R8": 110, "R4": 70, "R223": 0, "R2": 40, "R135": 0, "R1": 0,
            "CHIFF": 40, "SPEECH": 50, "SPREAD": 40, "AIR": 25, "WIND": 30, "TREM": 0, "TRATE": 60,
            "CELESTE": 0,
            "PERC": 0, "PDEC": 40, "MTUN": 0, "KCLK": 0, "MCHR": 0, "MIXT": 0, "ROTR": 0, "RSPD": 30,
            "BRTH": 0, "TURB": 70, "BREK": 0, "BDEP": 64, "PRES": 0, "BLOM": 0, "EDGE": 0, "PVEL": 0}
NO_LFO = ("BLOM", "EDGE", "PVEL")         # v0.5: on FM Tone's 235..237 (ATK, FDBK, VARY), no modulation
BIPOLAR = ()
PAGE_TITLES = tuple(PAGES)
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
# FASCIA's sound's records ORGAN leaves unused: named "-" and left out of the LFO list on an ORGAN track
UNUSED_RECORDS = tuple(sorted(({r for r, _s, _l, _t in FM.SLOTS.values()} | set(FM.UNUSED_RECORDS))
                              - {SLOTS[c][0] for c in CONTROLS}))
FM_SLOT_FIRST, FM_SLOT_LAST, FM_OWNED = FM.FM_SLOT_FIRST, FM.FM_SLOT_LAST, FM.FM_OWNED
# v0.5: a v0.4 ORGAN sound's words on pages 3 and 4's records (stock's record defaults: dnfw.organ.live
# LEGACY_WORDS, held equal by test_organ_machines). The DSP reads them as both pages at 0; the
# ColdFire's first turn of one of their knobs writes DEFAULTS on all 16 (fmt.c smp_quant)
LEGACY_FIRST = 16
LEGACY_WORDS = (0x4000, 0x4000, 0x0000, 0x4000, 0x4000, 0x4000, 0x4000, 0x4000,
                0x4000, 0x3200, 0x3200, 0x3200, 0x3200, 0x0000, 0x0000, 0x0000)

assert len(CONTROLS) == 32 and len(set(SLOTS[c][0] for c in CONTROLS)) == 32
assert not set(UNUSED_RECORDS) & {SLOTS[c][0] for c in CONTROLS}
assert {c for c in CONTROLS if RIDES[c] in FM.NO_LFO} == set(NO_LFO)


def is_choice(c: str) -> bool:
    return c in CHOICES


def knob(c: str, word: int) -> int:
    return FM.knob(RIDES[c], word)


def option(c: str, k: int) -> int:
    n = len(CHOICES[c])
    return min((min(max(k, 0), 127) * n) >> 7, n - 1)


def word_of(c: str, k: int) -> int:
    return FM.word_of(RIDES[c], k)


def rep_word(c: str, o: int) -> int:
    ks = [k for k in range(128) if option(c, k) == o]
    return word_of(c, (ks[0] + ks[-1]) // 2)


def default_words() -> dict[str, int]:
    """the words MACHINE SEL writes (rec.c smp_machine_commit): DEFAULTS, STOP's at its option's middle"""
    out = {c: word_of(c, DEFAULTS[c]) for c in CONTROLS}
    for c in CHOICES:
        out[c] = rep_word(c, option(c, DEFAULTS[c]))
    return out


def c_header() -> str:
    """the tables csrc/ reads (wr_gen.h), as FASCIA's (dnfw.fascia.machines.c_header), prefix org_"""
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
        raise ValueError("an ORGAN name is too long for its box, the header or its label")
    dw = default_words()

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* ORGAN (dnfw.organ.machines) */",
        f"#define ORG_TYPE {TYPE}", f"#define ORG_KIND {KIND}", f"#define ORG_N {len(CONTROLS)}",
        f"#define ORG_PAGES {len(PAGES)}",
        f"static const unsigned short org_rid[ORG_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char org_slot[ORG_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char org_lo[ORG_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char org_top[ORG_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char org_choices[ORG_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char org_choice_at[ORG_N] = {{{arr(at)}}};",
        f"static const char org_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char org_choice_box[{len(boxes)}][5] = {{{', '.join(q + b + q for b in boxes)}}};",
        f"static const unsigned char org_bipolar[ORG_N] = {{{arr(0 for _c in CONTROLS)}}};",
        f"static const char org_label[ORG_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short org_default[ORG_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define ORG_LEGACY_FIRST {LEGACY_FIRST}",
        f"static const unsigned short org_legacy[ORG_N - ORG_LEGACY_FIRST] = {{{arr(LEGACY_WORDS)}}};",
        "",
    ])
