"""RUBBER's (v0.24; GLASS's until v0.23) names on the FLTR page (RIFT v0.18; PING's P2 mechanism from the DN2 mk2 mod).

A GLASS (6) track's FLTR page is Multi-Mode's page (`dnfw.glass.coldfire`): the same records, which the
DSP side reads as GLASS's controls (`dnfw.glass.live`). While the active track's filter is GLASS,
`glass_names` (csrc/waverider/page.c, from the UI loop's poll) points the records whose meaning changes at
GLASS's names, so the page, the LFO and modulation destination lists and the header's parameter line say
what the knob does; the stock pointers go back as soon as it is not.

    page 1   ATK  DEC  .    .     /  FREQ RES  DRIV ENV     (v0.24: RUBBER)
    page 2   .    ABND DBND KEY.T /  BASE WDTH ...
"""

from __future__ import annotations

FILTER = 6
SETS = {6: {47: ("Attack Bend", "ABND"),     # the filter envelope's Sustain Level, on page 2: 0 exponential, 64 straight, 127 logarithmic
            48: ("Decay Bend", "DBND"),      # ... Release Time, on page 2: the same, on the decay
            38: ("Drive", "DRIV")}}          # Type: RUBBER's input level into the chip (v0.24)


def ids() -> list[int]:
    return sorted({rid for names in SETS.values() for rid in names})


def c_header() -> str:
    q = chr(34)
    order = ids()
    filters = sorted(SETS)

    def row(t, col):
        return "{" + ", ".join(q + SETS[t][r][col] + q if r in SETS[t] else "0" for r in order) + "}"
    return (f"#define GLASS_SETS {len(filters)}\n"
            f"static const signed char glass_filters[GLASS_SETS] = {{{', '.join(map(str, filters))}}};\n"
            f"#define GLASS_NAMED {len(order)}\n"
            f"static const unsigned short glass_named_ids[GLASS_NAMED] = {{{', '.join(map(str, order))}}};\n"
            f"static const char *const glass_named_long[GLASS_SETS][GLASS_NAMED] = "
            f"{{{', '.join(row(t, 0) for t in filters)}}};\n"
            f"static const char *const glass_named_short[GLASS_SETS][GLASS_NAMED] = "
            f"{{{', '.join(row(t, 1) for t in filters)}}};\n")
