"""SPALL on the ColdFire: its machine type, its names, and the records its sixteen controls ride.
No numpy: the build imports this.

Page 1, SYN1 PARTICLES: TYPE SIZE DENS GAP / EDGE CLMP MEM LEV.
Page 2, SYN2 SURFACE: TUNE SPRD ALG FRQA / FRQB RING COUP MIX. A track is one machine or another, so
they ride FASCIA's records as ORGAN's first sixteen do (CONTOUR's way).
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 26                                  # after CONTOUR's 25
KIND = TYPE - 4
LONG, SHORT = "Spall", "SPL"
LISTED = True

PAGES = {"SYN1 PARTICLES": ("TYPE", "SIZE", "DENS", "GAP", "EDGE", "CLMP", "MEM", "LEV"),
         "SYN2 SURFACE": ("TUNE", "SPRD", "ALG", "FRQA", "FRQB", "RING", "COUP", "MIX")}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
RIDES = dict(zip(CONTROLS, list(OM.RIDES.values())[:len(CONTROLS)]))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
TYPES = ("IMP", "DUST", "TONE", "CHIP")
ALGS = ("SUM", "RING", "SCAN")
CHOICES = {"TYPE": TYPES, "ALG": ALGS}
LABELS = {c: c for c in CONTROLS}
LONG_NAMES = {"TYPE": "Particle Type", "SIZE": "Particle Size", "DENS": "Density", "GAP": "Gap", "EDGE": "Edge",
              "CLMP": "Clump", "MEM": "Memory", "LEV": "Level", "TUNE": "Tune", "SPRD": "Spread",
              "ALG": "Oscillator Algorithm", "FRQA": "Resonator A", "FRQB": "Resonator B", "RING": "Ring Time",
              "COUP": "Coupling", "MIX": "Ring Mix"}
BOX = {"TYPE": "TYPE", "ALG": "ALG"}
OPT_DEFAULTS = {"TYPE": 0, "ALG": 2}
KNOB_DEFAULTS = {"SIZE": 40, "DENS": 56, "GAP": 40, "EDGE": 90, "CLMP": 30, "MEM": 0, "LEV": 100,
                 "TUNE": 64, "SPRD": 30, "FRQA": 60, "FRQB": 96, "RING": 60, "COUP": 20, "MIX": 80}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ("TUNE",)
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
    """the tables csrc/ reads, as CONTOUR's, prefix spl_"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    names: list[str] = []
    at = []
    for c in CONTROLS:
        at.append(len(names) if is_choice(c) else 0)
        if is_choice(c):
            names += list(CHOICES[c])
    if any(len(n) > 5 for n in names) or any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a SPALL name is too long for its box or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO] or [0]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* SPALL (dnfw.spall.machines) */",
        f"#define SPL_TYPE {TYPE}", f"#define SPL_KIND {KIND}", f"#define SPL_N {len(CONTROLS)}",
        f"#define SPL_PAGES {len(PAGES)}",
        f"static const unsigned short spl_rid[SPL_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char spl_slot[SPL_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char spl_lo[SPL_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char spl_top[SPL_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char spl_choices[SPL_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char spl_choice_at[SPL_N] = {{{arr(at)}}};",
        f"static const char spl_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char spl_choice_box[{len(names)}][5] = {{{', '.join(q + n[:4] + q for n in names)}}};",
        f"static const unsigned char spl_bipolar[SPL_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char spl_label[SPL_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short spl_default[SPL_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define SPL_NOLFO_N {len(nolfo)}",
        f"static const unsigned short spl_nolfo[SPL_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
