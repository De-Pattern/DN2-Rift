"""LIGATURE on the ColdFire: its machine type, its names, and the records its 32 controls ride. The table
the ColdFire's generated C header (dnfw.waverider.pages) and the DSP program (dnfw.ligature.program,
through organ.live.RIDES) read. No numpy: the build imports this.

A track is one machine or another, so LIGATURE rides FASCIA's records, in ORGAN's order
(organ.live.RIDES): page 1 PATCH (a choice: the wiring) and the voice's seven knobs, pages 2-4 the
twelve blocks' two settings each, every one an offset from its patch's own value (64: the patch as
made), so shown -64..+63. The last three ride FM Tone's 235..237 (no modulation).

The panel's labels use only the characters stock's own labels use (letters, digits, + - and space).
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 21                                  # after SILT's 20
KIND = TYPE - 4
LONG, SHORT = "Ligature", "LIG"
LISTED = True

PATCH_NAMES = ("INIT", "SYNC LD", "DX BELL", "PH DIST", "DRONE", "TANGLE", "SH BLIP", "TOMSKIN", "PLONK",
               "MANGRVE", "SPLIT", "CREASE", "BENJOLN")      # dnfw.ligature.live.PATCHES' names
PAGES = {
    "SYN1 PATCH": ("PATCH", "TUNE", "FINE", "LFO1", "LFO2", "VSNS", "DRIV", "LEVL"),
    "SYN2 BLOCKS 1-4": tuple(f"S{i}{x}" for i in (1, 2, 3, 4) for x in "AB"),
    "SYN3 BLOCKS 5-8": tuple(f"S{i}{x}" for i in (5, 6, 7, 8) for x in "AB"),
    "SYN4 BLOCKS 9-12": tuple(f"S{i}{x}" for i in (9, 10, 11, 12) for x in "AB"),
}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
RIDES = dict(zip(CONTROLS, OM.RIDES.values()))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
CHOICES = {"PATCH": PATCH_NAMES}
LABELS = {"PATCH": "PATCH", "TUNE": "TUNE", "FINE": "FINE", "LFO1": "LFO1", "LFO2": "LFO2", "VSNS": "VSNS",
          "DRIV": "DRIVE", "LEVL": "LEVEL",
          **{f"S{i}{x}": f"{i}{x}" for i in range(1, 13) for x in "AB"}}
LONG_NAMES = {"PATCH": "Patch", "TUNE": "Tune", "FINE": "Fine Tune", "LFO1": "LFO 1 Rate", "LFO2": "LFO 2 Rate",
              "VSNS": "Velocity Sense", "DRIV": "Drive", "LEVL": "Level",
              **{f"S{i}{x}": f"Block {i} Setting {x}" for i in range(1, 13) for x in "AB"}}
BOX = {"INIT": "INIT", "SYNC LD": "SYNC", "DX BELL": "DXBL", "PH DIST": "PHDS", "DRONE": "DRON",
       "TANGLE": "TANG", "SH BLIP": "SHBL", "TOMSKIN": "TOMS", "PLONK": "PLNK", "MANGRVE": "MANG",
       "SPLIT": "SPLT", "CREASE": "CRES", "BENJOLN": "BENJ"}
OPT_DEFAULTS = {"PATCH": 0}
KNOB_DEFAULTS = {"TUNE": 64, "FINE": 64, "LFO1": 40, "LFO2": 60, "VSNS": 64, "DRIV": 0, "LEVL": 100,
                 **{f"S{i}{x}": 64 for i in range(1, 13) for x in "AB"}}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ("TUNE", "FINE") + tuple(f"S{i}{x}" for i in range(1, 13) for x in "AB")
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
    """the tables csrc/ reads (wr_gen.h), as SILT's, prefix lig_"""
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
        raise ValueError("a LIGATURE name is too long for its box, the header or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* LIGATURE (dnfw.ligature.machines) */",
        f"#define LIG_TYPE {TYPE}", f"#define LIG_KIND {KIND}", f"#define LIG_N {len(CONTROLS)}",
        f"#define LIG_PAGES {len(PAGES)}",
        f"static const unsigned short lig_rid[LIG_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char lig_slot[LIG_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char lig_lo[LIG_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char lig_top[LIG_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char lig_choices[LIG_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char lig_choice_at[LIG_N] = {{{arr(at)}}};",
        f"static const char lig_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char lig_choice_box[{len(boxes)}][5] = {{{', '.join(q + b + q for b in boxes)}}};",
        f"static const unsigned char lig_bipolar[LIG_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char lig_label[LIG_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short lig_default[LIG_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define LIG_NOLFO_N {len(nolfo)}",
        f"static const unsigned short lig_nolfo[LIG_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
