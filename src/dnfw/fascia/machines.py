"""FASCIA on the ColdFire: its machine type, its names, and where its 32 controls sit
(RIFT: pass 3's four pages; the text below describes v2's 24 where it says so)
(docs/fascia.md, "The ColdFire side"). The one table both the ColdFire's generated C
header (dnfw.waverider.pages) and the FASCIA DSP program read.

Like every machine of ours, FASCIA's controls ride stock parameter records, so they are
p-lockable, LFO destinations, slid, saved with the sound and copied as any stock control.
The panel is `dnfw.fascia.model`'s (PAGES, CHOICES, DEFAULTS): mirrored here because this
module is imported by the build itself (dnfw.mods.waverider, also run in the browser
patcher), which must not need numpy or scipy; test_fascia_coldfire holds the two equal.

Where the 24 go (owner, 2026-11-08: no CC on the controls riding FM Tone's spare slots):

- the 19 continuous controls on records whose range is exactly 0..0x7f00, so the DSP reads
  the panel's 0..127 as `word >> 8` with nothing rescaled: WaveTone's ten with a CC (LEV1,
  LEV2, DRIF, ATK, HOLD, DEC, NLEV, BASE, WDTH, CHAR), its MAST and FINE (no CC, on no stock
  page), and FM Tone's spare records 227..233 on slots 50..56 (no CC);
- the 5 choice controls on WaveTone's records of 0..100 or 0..120 (WAV1, WAV2, PD1, PD2,
  OFS1, all with a CC): a choice needs no 128 steps. Its knob is the value over the record's
  span x 127, rounded, as the Monomachine's (`knob()` below, page.c mnm_knob), and the
  option `(knob * n) >> 7`, which is the model's `choice()`.

Only 12 of WaveTone's 25 records span 0..127 (TUN1/TUN2 4..124, WAV1/WAV2 0..120, PD1/PD2/
OFS1/OFS2 0..100; TBL1, TBL2, MOD, RSET, TYPE a few steps), hence FM Tone's seven.
FM Tone's 235..237 are not used: their modulation mask is 0 (no LFO destination).
"""

from __future__ import annotations

TYPE = 18                                 # the next free machine type (PERC 5, MnM 6 7 14..16, samples 8..13, BOUNCE 17)
KIND = TYPE - 4                           # is_wr's answer (dnfw.waverider.pages)
LONG, SHORT = "Fascia", "FSC"             # MACHINE SEL's names (as "Perc"/"PRC", "Oneshot"/"ONE")
# v0.45 (coordinator, 2026-11-08: v0.44 froze units when BOUNCE was picked in MACHINE SEL, cause
# unknown): FASCIA's MACHINE SEL entry is this one switch. Listed, it is a 19th entry in group 3,
# next to the Monomachine's, so it adds no divider row. False leaves type 18 fully built but
# unlisted (list as v0.44's).
LISTED = True

# -- the panel, as dnfw.fascia.model has it (held equal by test_fascia_coldfire) -------------
# RIFT (owner, 2026-11-12): pass 3's four pages, the engine's own 32 controls
TYPES = ("STRIKE", "BLOW", "BOW", "DUST", "PULSE", "TZFM")
BODIES = ("MEMB", "PLATE", "BAR", "VIBE", "CHIME", "BELL", "GLASS", "TUBE", "STRING", "OFF")
CLICKS = ("SNAP", "TICK", "NOISE", "THUMP")
XMODS = ("EXCITE", "BEND", "CHOKE", "TRADE")
PAGES = {
    "SYN1 EXCITERS": ("TYPA", "TYPB", "HARD", "DUST", "TZFM", "BEND", "MIX", "DEC"),
    "SYN2 RESONATORS": ("BODA", "BODB", "TUNE", "GEOM", "MATL", "POS", "COUP", "DAMP"),
    "SYN3 SPECTRAL": ("MORPH", "FORM", "SHIFT", "RING", "SIDE", "FOLD", "LPG", "CHAR"),
    "SYN4 ONSET/INTERACT": ("ATK", "CLIK", "CTYP", "XMOD", "FDBK", "BUZZ", "WATR", "VARY"),
}
CHOICES = {"TYPA": TYPES, "TYPB": TYPES, "BODA": BODIES[:-1], "BODB": BODIES, "CTYP": CLICKS, "XMOD": XMODS}
# RIFT v0.4 (owner, 2026-11-15: a new track must start from a musical place): MACHINE SEL and
# TRK + CLEAR start FASCIA as the demo's vibraphone (fascia_audition 03_vibraphone): STRIKE alone
# (MIX 0) into a VIBE bar over a TUBE resonator, CHAR 0. dnfw.fascia.model.DEFAULTS is the same.
DEFAULTS = {
    "TYPA": 0, "TYPB": 1, "HARD": 42, "DUST": 20, "TZFM": 0, "BEND": 10, "MIX": 0, "DEC": 20,
    "BODA": 49, "BODB": 96, "TUNE": 64, "GEOM": 64, "MATL": 96, "POS": 28, "COUP": 70, "DAMP": 34,
    "MORPH": 0, "FORM": 0, "SHIFT": 64, "RING": 0, "SIDE": 40, "FOLD": 0, "LPG": 20, "CHAR": 0,
    "ATK": 0, "CLIK": 0, "CTYP": 0, "XMOD": 0, "FDBK": 0, "BUZZ": 0, "WATR": 0, "VARY": 40,
}

# -- the slot table: control -> (record id, frame slot, low, top) -----------------------------
# The stock record's own range (0x401f7f94 + 60 id: +4 slot, +8 min, +12 max): value =
# clamp((word >> 8) - low, 0, top); on the DSP the frame word is at 168 + 2 slot + 146 t.
# RIFT: the 16 continuous and 5 choice controls v2 shared with pass 3 keep v2's records; the
# rest: FORM, CLIK, CHAR on WaveTone's DEC, BASE, CHAR (freed by v2's SKIN, CLIK, DRIVE);
# CTYP on OFS2 (0..100); RING on FM Tone's 234; ATK, FDBK, VARY on FM Tone's 235..237 (their
# modulation scale made FM Tone's, coldfire.FSC_MOD_RECORDS); WATR, FOLD, SIDE on FM Tone's
# 208..210 (0..0x7ffe: word >> 8 is 0..127).
SLOTS = {
    # SYN1 EXCITERS
    "TYPA": (239, 26, 0, 120),           # WAV1  CC 41
    "TYPB": (243, 32, 0, 120),           # WAV2  CC 45
    "HARD": (241, 30, 0, 127),           # LEV1  CC 43
    "DUST": (227, 50, 0, 127),           # FM Tone's, no CC
    "TZFM": (228, 51, 0, 127),           # FM Tone's, no CC
    "BEND": (229, 52, 0, 127),           # FM Tone's, no CC
    "MIX": (230, 53, 0, 127),            # FM Tone's, no CC
    "DEC": (253, 40, 0, 127),            # ATK   CC 56
    # SYN2 RESONATORS
    "BODA": (240, 29, 0, 100),           # PD1   CC 42
    "BODB": (244, 35, 0, 100),           # PD2   CC 46
    "TUNE": (245, 36, 0, 127),           # LEV2  CC 47
    "GEOM": (261, 48, 0, 127),           # MAST, no CC
    "MATL": (231, 54, 0, 127),           # FM Tone's, no CC
    "POS": (232, 55, 0, 127),            # FM Tone's, no CC
    "COUP": (233, 56, 0, 127),           # FM Tone's, no CC
    "DAMP": (254, 41, 0, 127),           # HOLD  CC 57
    # SYN3 SPECTRAL
    "MORPH": (252, 38, 0, 127),          # DRIF  CC 55
    "FORM": (255, 42, 0, 127),           # DEC   CC 58
    "SHIFT": (258, 45, 0, 127),          # WDTH  CC 61
    "RING": (234, 57, 0, 127),           # FM Tone's, no CC
    "SIDE": (210, 60, 0, 127),           # FM Tone's (0..0x7ffe), no CC
    "FOLD": (209, 59, 0, 127),           # FM Tone's (0..0x7ffe), no CC
    "LPG": (256, 43, 0, 127),            # NLEV  CC 59
    "CHAR": (260, 47, 0, 127),           # CHAR  CC 63
    # SYN4 ONSET/INTERACT
    "ATK": (235, 62, 0, 127),            # FM Tone's, no CC
    "CLIK": (257, 44, 0, 127),           # BASE  CC 60
    "CTYP": (250, 34, 0, 100),           # OFS2  CC 52
    "XMOD": (246, 28, 0, 100),           # OFS1  CC 48
    "FDBK": (236, 63, 0, 127),           # FM Tone's, no CC
    "BUZZ": (262, 49, 0, 127),           # FINE, no CC
    "WATR": (208, 58, 0, 127),           # FM Tone's (0..0x7ffe), no CC
    "VARY": (237, 64, 0, 127),           # FM Tone's, no CC
}
CC = {"TYPA": 41, "TYPB": 45, "HARD": 43, "DEC": 56, "BODA": 42, "BODB": 46, "TUNE": 47,
      "DAMP": 57, "MORPH": 55, "FORM": 58, "SHIFT": 61, "LPG": 59, "CHAR": 63, "CLIK": 60,
      "CTYP": 52, "XMOD": 48,
      "WATR": 70, "FOLD": 71, "SIDE": 72, "ATK": 75, "FDBK": 76, "VARY": 77}  # the stock records' MIDI CC; the rest have none
# RIFT: ATK, FDBK and VARY ride FM Tone's 235..237, whose modulation mask is 0: p-lockable and
# slid, not LFO destinations (set-and-forget controls; opening the mask is a follow-up)
NO_LFO = ("ATK", "FDBK", "VARY")

CONTROLS = tuple(c for page in PAGES.values() for c in page)          # page order, 24
PAGE_TITLES = tuple(PAGES)                                             # "SYN1 EXCITE", ...
# the header's line (the descriptor's subtitle, shown with the page's number): the machine
# and the page's name, as stock shows "WaveTone (1/3)"
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
BIPOLAR = ("TUNE", "GEOM", "SHIFT")                            # shown -64..+63, 0 at 64
# a choice's name in its box: four characters fit inside it in the grid's label font (five
# touched its border in the emulator); the header and SYN held show the whole name
BOX = {"STRIKE": "STRK", "PULSE": "PULS", "PLATE": "PLAT", "CHIME": "CHIM", "GLASS": "GLAS",
       "STRING": "STRG", "EXCITE": "EXCT", "CHOKE": "CHOK", "TRADE": "TRAD", "NOISE": "NOIS",
       "THUMP": "THMP"}
LONG_NAMES = {
    "TYPA": "Exciter A", "TYPB": "Exciter B", "HARD": "Hardness", "DUST": "Dust",
    "TZFM": "Thru-Zero FM", "BEND": "Bend", "MIX": "Exciter Mix", "DEC": "Exciter Decay",
    "BODA": "Body A", "BODB": "Body B", "TUNE": "Tune", "GEOM": "Geometry",
    "MATL": "Material", "POS": "Position", "COUP": "Coupling", "DAMP": "Damping",
    "MORPH": "Morph", "FORM": "Formant", "SHIFT": "Freq Shift", "RING": "Ring Mod",
    "SIDE": "Sideband", "FOLD": "Fold", "LPG": "Low Pass Gate", "CHAR": "Character",
    "ATK": "Attack", "CLIK": "Click", "CTYP": "Click Type", "XMOD": "Cross Mod",
    "FDBK": "Feedback", "BUZZ": "Buzz", "WATR": "Water", "VARY": "Variation",
}

# the records FASCIA's sound owns beyond WaveTone's: FM Tone's on slots 50..64 (page 0).
# param_set_slot_to_id answers slots 50..64 of a FASCIA sound with FM Tone's records, and the
# ownership test accepts exactly these (dnfw.waverider.coldfire slot_shim, canon_valid)
FM_SLOT_FIRST, FM_SLOT_LAST = 50, 64
FM_OWNED = ((208, 211), (227, 237))       # id runs: FM Tone's records on slots 58..61, 50..57 and 62..64
FM_USED = tuple(SLOTS[c][0] for c in CONTROLS if SLOTS[c][0] < 238)
UNUSED_RECORDS = tuple(sorted({*range(238, 263), *range(208, 212), *range(227, 238)}
                              - {r for r, _s, _lo, _t in SLOTS.values()}))


def is_choice(c: str) -> bool:
    return c in CHOICES


def knob(c: str, word: int) -> int:
    """a record word -> the panel's 0..127, as the page, the quant and the DSP read it"""
    rid, _slot, lo, top = SLOTS[c]
    v = min(max((word >> 8) - lo, 0), top)
    return v if top == 127 else (v * 254 + top) // (2 * top)


def option(c: str, k: int) -> int:
    """the option a 0..127 knob picks: (k n) >> 7, the model's choice()"""
    n = len(CHOICES[c])
    return min((min(max(k, 0), 127) * n) >> 7, n - 1)


def word_of(c: str, k: int) -> int:
    """the record word whose knob is K (or the nearest: 0..100 records have 101 values)"""
    rid, _slot, lo, top = SLOTS[c]
    if top == 127:
        return (lo + k) << 8
    v = min(range(top + 1), key=lambda v: (abs((v * 254 + top) // (2 * top) - k), v))
    return (lo + v) << 8


def rep_word(c: str, o: int) -> int:
    """the record word in the middle of option O's knob span: what a detent writes"""
    ks = [k for k in range(128) if option(c, k) == o]
    return word_of(c, (ks[0] + ks[-1]) // 2)


def default_words() -> dict[str, int]:
    """the words MACHINE SEL writes (rec.c smp_machine_commit): the model's DEFAULTS"""
    return {c: word_of(c, DEFAULTS[c]) for c in CONTROLS}


def c_header() -> str:
    """the tables csrc/ reads (wr_gen.h): the pages, the records, their ranges, choices,
    names and defaults, in page order"""
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
    if any(len(b) > 4 for b in boxes) or any(len(n) > 7 for n in names):
        raise ValueError("a FASCIA option's name is too long for its box or the header")
    dw = default_words()

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* FASCIA (dnfw.fascia.machines) */",
        f"#define FSC_TYPE {TYPE}", f"#define FSC_KIND {KIND}", f"#define FSC_N {len(CONTROLS)}",
        f"#define FSC_PAGES {len(PAGES)}",
        f"#define FSC_TUNE_J {CONTROLS.index('TUNE')}",
        f"static const unsigned short fsc_rid[FSC_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char fsc_slot[FSC_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char fsc_lo[FSC_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char fsc_top[FSC_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char fsc_choices[FSC_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char fsc_choice_at[FSC_N] = {{{arr(at)}}};",
        f"static const char fsc_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char fsc_choice_box[{len(boxes)}][5] = {{{', '.join(q + b + q for b in boxes)}}};",
        f"static const unsigned char fsc_bipolar[FSC_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char fsc_label[FSC_N][6] = {{{', '.join(q + c + q for c in CONTROLS)}}};",
        f"static const unsigned short fsc_default[FSC_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"#define FSC_NOLFO_N {len(NO_LFO)}",
        f"static const unsigned short fsc_nolfo[FSC_NOLFO_N] = {{{arr(SLOTS[c][0] for c in NO_LFO)}}};",
        "",
    ])
