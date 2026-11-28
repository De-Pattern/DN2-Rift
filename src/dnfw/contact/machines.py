"""CONTACT on the ColdFire (RIFT, the FX machine's phase 0; owner 2026-11-27: the TRANSDUCE concept's
CONTACT first, "built cheaply", FASCIA's components; claude/rift-fx-contact-plan.md): its machine type,
its names and the records its sixteen controls ride. No numpy: the build imports this.

An FX machine: a track whose voice is another sound, chosen by SRC (the input, or another track's
block, as FLEX's selector), trimmed by GAIN, played while the track has a note, through the track's
own filter, amp, pan, sends, LFOs and locks. Phase 0 (THRU): SRC, GAIN and LEV; the rest of the
controls are CONTACT's to come and do nothing yet (drawn as such).

Page 1, FX1 INPUT: SRC GAIN SENS EXC / CLST TONE MIX LEV.
Page 2, FX2 BODY: BODY TUNE DCAY DAMP / SPRD SIZE BRIT WATR.
A track is one machine or another, so they ride ORGAN's records as SPALL's do.
"""

from __future__ import annotations

from ..fascia import machines as FM
from ..organ import machines as OM

TYPE = 27                                  # after SPALL's 26
KIND = TYPE - 4
LONG, SHORT = "Contact", "CNT"
LISTED = True
FX = True                                  # MACHINE SEL's FX section (coldfire.FX_GROUP), as PLATEAU

SOURCES = ("IN", "IN L", "IN R") + tuple(f"T{n}" for n in range(1, 17))   # SRC: the input (L+R, L, R), a track
PAGES = {"FX1 INPUT": ("SRC", "GAIN", "SENS", "EXC", "CLST", "TONE", "MIX", "LEV"),
         "FX2 BODY": ("BODY", "TUNE", "DCAY", "DAMP", "SPRD", "SIZE", "BRIT", "WATR")}
CONTROLS = tuple(c for page in PAGES.values() for c in page)
LIVE = ("SRC", "GAIN", "LEV")             # phase 0: what does something
RIDES = dict(zip(CONTROLS, list(OM.RIDES.values())[:len(CONTROLS)]))
SLOTS = {c: FM.SLOTS[RIDES[c]] for c in CONTROLS}
EXCS = ("THRU",)                           # phase 0: the source as it is
BODIES = ("NONE",)
CHOICES = {"SRC": SOURCES, "EXC": EXCS, "BODY": BODIES}
LABELS = {c: c for c in CONTROLS}
LONG_NAMES = {"SRC": "Source", "GAIN": "Input Gain", "SENS": "Sensitivity", "EXC": "Exciter",
              "CLST": "Cluster", "TONE": "Tone", "MIX": "Mix", "LEV": "Level", "BODY": "Body",
              "TUNE": "Tune", "DCAY": "Decay", "DAMP": "Damping", "SPRD": "Spread", "SIZE": "Size",
              "BRIT": "Brightness", "WATR": "Water"}
BOX = {"SRC": "SRC", "EXC": "EXC", "BODY": "BODY"}
OPT_DEFAULTS = {"SRC": 0, "EXC": 0, "BODY": 0}
KNOB_DEFAULTS = {"GAIN": 96, "SENS": 64, "CLST": 64, "TONE": 64, "MIX": 127, "LEV": 100,
                 "TUNE": 64, "DCAY": 64, "DAMP": 64, "SPRD": 32, "SIZE": 64, "BRIT": 64, "WATR": 0}
NO_LFO = tuple(c for c in CONTROLS if RIDES[c] in FM.NO_LFO)
BIPOLAR = ("CLST", "TUNE")
PAGE_TITLES = tuple(PAGES)
PAGE_SUBTITLES = tuple(f"{LONG} {t.split(' ', 1)[1].capitalize()}" for t in PAGES)
UNUSED_RECORDS = tuple(r for r in (FM.SLOTS[x][0] for x in FM.CONTROLS) if r not in {SLOTS[c][0] for c in CONTROLS}) \
    + tuple(OM.UNUSED_RECORDS)
FM_SLOT_FIRST, FM_SLOT_LAST, FM_OWNED = FM.FM_SLOT_FIRST, FM.FM_SLOT_LAST, FM.FM_OWNED
GAIN_UNITY = 96                            # GAIN: 0 off, 1..127 = (k - 96) x 12/31 dB (96 0 dB, 127 +12 dB)

assert set(KNOB_DEFAULTS) | set(OPT_DEFAULTS) == set(CONTROLS)
assert set(LIVE) <= set(CONTROLS)


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


def gain_db(k: int) -> float | None:
    """GAIN's dB (None: off)"""
    return None if k <= 0 else (k - GAIN_UNITY) * 12.0 / 31.0


def c_header() -> str:
    """the tables csrc/ reads, as SPALL's, prefix cnt_"""
    q = chr(34)
    rows = [SLOTS[c] for c in CONTROLS]
    names: list[str] = []
    at = []
    for c in CONTROLS:
        at.append(len(names) if is_choice(c) else 0)
        if is_choice(c):
            names += list(CHOICES[c])
    if any(len(n) > 5 for n in names) or any(len(x) > 5 for x in LABELS.values()):
        raise ValueError("a CONTACT name is too long for its box or its label")
    dw = default_words()
    nolfo = [SLOTS[c][0] for c in NO_LFO] or [0]

    def arr(xs):
        return ", ".join(str(x) for x in xs)
    return "\n".join([
        "/* CONTACT (dnfw.contact.machines) */",
        f"#define CNT_TYPE {TYPE}", f"#define CNT_KIND {KIND}", f"#define CNT_N {len(CONTROLS)}",
        f"#define CNT_PAGES {len(PAGES)}",
        f"static const unsigned short cnt_rid[CNT_N] = {{{arr(r for r, _s, _l, _t in rows)}}};",
        f"static const unsigned char cnt_slot[CNT_N] = {{{arr(s for _r, s, _l, _t in rows)}}};",
        f"static const unsigned char cnt_lo[CNT_N] = {{{arr(lo for _r, _s, lo, _t in rows)}}};",
        f"static const unsigned char cnt_top[CNT_N] = {{{arr(t for _r, _s, _l, t in rows)}}};",
        f"static const unsigned char cnt_choices[CNT_N] = {{{arr(len(CHOICES[c]) if is_choice(c) else 0 for c in CONTROLS)}}};",
        f"static const unsigned char cnt_choice_at[CNT_N] = {{{arr(at)}}};",
        f"static const char cnt_choice_name[{len(names)}][8] = {{{', '.join(q + n + q for n in names)}}};",
        f"static const char cnt_choice_box[{len(names)}][5] = {{{', '.join(q + n[:4] + q for n in names)}}};",
        f"static const unsigned char cnt_bipolar[CNT_N] = {{{arr(int(c in BIPOLAR) for c in CONTROLS)}}};",
        f"static const char cnt_label[CNT_N][6] = {{{', '.join(q + LABELS[c] + q for c in CONTROLS)}}};",
        f"static const unsigned short cnt_default[CNT_N] = {{{arr(dw[c] for c in CONTROLS)}}};",
        f"static const unsigned char cnt_live[CNT_N] = {{{arr(int(c in LIVE) for c in CONTROLS)}}};",
        f"#define CNT_NOLFO_N {len(nolfo)}",
        f"static const unsigned short cnt_nolfo[CNT_NOLFO_N] = {{{arr(nolfo)}}};",
        "",
    ])
