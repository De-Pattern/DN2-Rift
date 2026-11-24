#!/usr/bin/env python3
"""RIFT's quick guide (site/rift-quick.html): a legend of every RIFT machine's controls laid out as
the Digitone's own pages (knobs A-D over E-H, each "PARAM: what it does"), quick starts, the FLEX
and SMEAR walk-throughs and tips, for people who don't want to read the manual yet.

Owner, 2026-11-24: "a kind of legend for the complex esoteric controls of the new engines ...
how to quickly set up flex tracks and record and playback ... how to use the smear ... visually
appealing ... more graphics for quick skimming and hunting for certain helpful tips". Served next
to the MANUAL button (both patchers) and linked from the manual's top.

    python3 scripts/gen_rift_quick.py [--out site/rift-quick.html]
"""
from __future__ import annotations

import argparse
import base64
import html
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGOS = ROOT / "src" / "dnfw" / "waverider" / "logos"
COVERS = "0.22"                         # the newest release the guide describes (not VERSION: a release in the making)

E = html.escape


def logo(name: str) -> str:
    p = LOGOS / f"{name}.png"
    if not p.exists():
        return ""
    b = base64.b64encode(p.read_bytes()).decode()
    return f'<img class="px" src="data:image/png;base64,{b}" alt="" width="92" height="64">'


# Each machine: (id, name, logo, one line, quick start, pages, extra html)
# A page: (title, [8 cells: (PARAM, what it does)])  -- cells in knob order A B C D / E F G H
MACHINES = [
    ("fascia", "FASCIA", "fascia", "Struck, bowed and blown bodies: an exciter sets one or two resonant bodies ringing.",
     "Pick BODA, set TUNE and DAMP. Then TYPA and HARD. Colour with MATL, POS, GEOM. Body B + COUP adds a second, related body.",
     [("SYN1 Exciters", [("TYPA", "Exciter A: STRIKE, BLOW, BOW, DUST, PULSE, TZFM"), ("TYPB", "Exciter B, the same six"),
                         ("HARD", "Mallet hardness / bow pressure / breath"), ("DUST", "Grit, rosin catches, impulse density"),
                         ("TZFM", "Through-zero FM: a metallic edge"), ("BEND", "Pitch glide as the body rings (drum skin)"),
                         ("MIX", "A only at 0, B only at 127"), ("DEC", "How long the exciter keeps exciting")]),
      ("SYN2 Resonators", [("BODA", "Body A: MEMB, PLATE, BAR, VIBE, CHIME, BELL, GLASS, TUBE, STRING"), ("BODB", "Body B (same types) or OFF"),
                           ("TUNE", "Pitch around the note; FUNC + turn: octaves"), ("GEOM", "Harmonic, woody ← → inharmonic, metallic"),
                           ("MATL", "Wood/skin (highs die) ↔ metal/glass (highs ring)"), ("POS", "Strike point: hollow centre ↔ bright edge"),
                           ("COUP", "How much A drives B"), ("DAMP", "Ring time: low rings long, high is a thud")]),
      ("SYN3 Spectral", [("MORPH", "Brightens or darkens the tail, same pitch"), ("FORM", "Vowel formants a e i o u"),
                         ("SHIFT", "Frequency shift ±2 kHz: beats to alien"), ("RING", "Ring mod A × B"),
                         ("SIDE", "TZFM modulator ratio"), ("FOLD", "Wavefolder"), ("LPG", "Darkens and quietens as it dies"),
                         ("CHAR", "Warm then gritty saturation")]),
      ("SYN4 Onset / interact", [("ATK", "Swell into the hit / bow rise"), ("CLIK", "A transient on top, sized by HARD"),
                                 ("CTYP", "SNAP, TICK, NOISE, THUMP"), ("XMOD", "A on B: EXCITE, BEND, CHOKE, TRADE"),
                                 ("FDBK", "B back into A: sustain, then howl"), ("BUZZ", "Snare wires, sitar buzz"),
                                 ("WATR", "Gurgling water-drum partials"), ("VARY", "Every hit a little different")])],
     [("Marimba", "BAR · STRIKE · HARD 50 · MATL low · DAMP 40"), ("Tubular bell", "CHIME · HARD 90 · DAMP 20"),
      ("Bowed glass", "GLASS · BOW · DEC high · HARD 40"), ("Snare", "MEMB · BUZZ high · CLIK SNAP"),
      ("Steel drum", "PLATE · WATR up"), ("Gong", "BELL + BODB PLATE · XMOD TRADE · a little FDBK")]),
    ("organ", "ORGAN", "organ", "A pipe organ: stops and drawbars, the pipes' breath and speech, rotor, and a flute you can blow.",
     "Choose a STOP and pull drawbars (8FT alone is the plainest; add 4FT and 2FT). Page 2 gives the pipes life. Send it to the reverb.",
     [("SYN1 Ranks", [("STOP", "FLUTE, NACHTHN, PRINCPL, GAMBA, TRUMPET"), ("16FT", "Octave below"), ("8FT", "The note"),
                      ("4FT", "Octave above"), ("NAZ", "12th: hollow quint"), ("2FT", "Two octaves up"), ("TIER", "17th: reedy Cornet with NAZ"),
                      ("1FT", "Sparkle on top")]),
      ("SYN2 Pipes", [("CHIFF", "Breathy puff at each note"), ("SPCH", "How slowly pipes speak"), ("SPRD", "Ranks detuned: big-organ chorus"),
                      ("AIR", "Wind noise under the tone"), ("WIND", "Unsteady bellows wobble"), ("TREM", "Tremulant depth"),
                      ("RATE", "Tremulant speed"), ("CELST", "A sharp rank beating: shimmer")]),
      ("SYN3 Attack", [("PERC", "Hammond-style ping"), ("PDEC", "Ping decay"), ("MTUN", "Mixture tuned down"), ("KCLK", "Key click"),
                       ("MCHR", "Mixture toward trumpet tone"), ("MIXT", "Glittering high crown"), ("ROTR", "Rotating speaker depth"),
                       ("RSPD", "Rotor speed, with spin-up lag")]),
      ("SYN4 Breath", [("BRTH", "Breath inside the tone: a played flute"), ("TURB", "Breath rate"), ("BREK", "Overblown voice break"),
                       ("BDEP", "Break depth"), ("PRES", "Blowing pressure"), ("BLOM", "Breath blooming into tone"),
                       ("EDGE", "Noise heard as it blooms"), ("PVEL", "Velocity blows harder")])],
     [("Plenum", "PRINCPL · 16 8 4 2 up · MIXT up"), ("Vox celeste", "GAMBA · 8FT only · CELST up"),
      ("Drawbar organ", "PERC 80 · KCLK 50 · ROTR 70"), ("Played flute", "FLUTE · BRTH 60 · BLOM 50 · EDGE 40 · PVEL up")]),
    ("silt", "SILT", "silt", "Material synthesis: strings, grains, rubber and molten fluid, played by ten gestures, alone or as a crowd.",
     "Start on page 4: MAT (what it is), GEST (what you do), MODE (one player or many). Then PRESS (how hard) and SPEED. Velocity and the trig's length play the gesture.",
     [("SYN1 Matter", [("PART", "Stiffness, grain size"), ("TENS", "Tension, brightness, bounce"), ("MASS", "Body size, weight"),
                       ("COHE", "Players apart ↔ locked (70 natural)"), ("VISC", "Damping: water ↔ honey"), ("GRAIN", "Grit and stroke length"),
                       ("DENS", "Crackle, extra players, drip rate"), ("BODY", "Resonating body")]),
      ("SYN2 Contact", [("PRESS", "Always: how hard"), ("SPEED", "Bow speed and all rates"), ("POS", "Edge ↔ middle"), ("ROSIN", "Grip"),
                        ("SCRAP", "Irregular friction"), ("SNAP", "Transient hardness"), ("AIR", "Breath noise"), ("INST", "How near it is to failing")]),
      ("SYN3 Structure", [("SPRD", "Cluster width"), ("VOICE", "How many players"), ("DRIFT", "Slow detune per player"), ("VIBR", "Vibrato"),
                          ("GLISS", "Glissando / scoop (centre 0)"), ("FORM", "Formant that rises with energy"), ("ROUGH", "Scattered strikes"),
                          ("MORPH", "Tonal ↔ particulate")]),
      ("SYN4 Config (p-lock per trig)", [("MAT", "FIBER, SILT, SKIN, FLUID"), ("GEST", "BOW SCRAPE STACC TREMO SPICC LEGNO GLISS FRACT SWELL QUAKE"),
                                         ("MODE", "SOLO, MASS, MASS-8, SWARM"), ("DIST", "NARROW, WIDE, BIMODAL, ASYM"),
                                         ("LOOP", "Re-trigger while held: OFF 16TH 8TH 4TH FREE"), ("SHAPE", "SOFT, LINEAR, EXP, CHAOTIC"),
                                         ("TUNE", "FREE, SCALE, MICRO, HARM"), ("QUAL", "ECO, NORMAL, DEEP (most CPU)")])],
     [("Stable to squeal", "raise PRESS × ROSIN"), ("Cluster", "SPRD × DRIFT × COHE in MASS"), ("Water to honey", "FLUID · VISC × TENS × SPEED"),
      ("Pluck to thud", "SKIN · SNAP × VISC")]),
    ("ligature", "LIGATURE", "ligature", "A patchable block synth: twelve small blocks wired together, 128 patches per project.",
     "Pick a factory PATCH (1-13) and play. To rewire, press [YES] on page 1.",
     [("SYN1 Patch", [("PATCH", "Which of 128 wirings (p-lockable)"), ("TUNE", "±24 semitones"), ("FINE", "±50 cents"), ("LFO1", "Rate of the LFO1 source"),
                      ("LFO2", "Rate of the LFO2 source"), ("VSNS", "Velocity on level"), ("DRIVE", "Soft clip on the output"), ("LEVEL", "Level")])],
     [("EDIT ([YES])", "A block · B type · C/D input A + amount · E/F input B + amount · G B-moves-a-setting · H output block"),
      ("Empty a block", "[FUNC] + [NO]"), ("Pages 2-4", "Two settings a block (1RISE, 3CUT…), offsets: 0 is the patch as wired"),
      ("A voice to build", "e.g. PHAS into WAVE, into LP (a SLOP on its B), into MULT (another SLOP on its B), OUT on the MULT")]),
    ("digidrum", "DIGIDRUM", "digidrum", "Digital drums: six voices on one track, picked per trig by TYPE.",
     "Set TYPE, then p-lock TYPE on each trig (BD on 1 and 9, SD on 5 and 13…): a whole kit on one track.",
     [("SYN1 Drum", [("TYPE", "BD, SD BASIC, SD VINTAGE, CP, CY, PC"), ("TUNE", "Pitch (64 the drum's own)"), ("PNCH", "Snap and weight at the front"),
                     ("DEC", "Amp decay"), ("O1", "Per TYPE (below)"), ("O2", "Per TYPE"), ("O3", "Per TYPE"), ("O4", "Per TYPE")]),
      ("SYN2 Tone", [("OVER", "Overdrive: warm → crushed"), ("EQF", "EQ band frequency"), ("EQG", "Boost / cut (64 flat)"), ("AMD", "Tremolo depth"),
                     ("AMF", "Tremolo rate (fast: AM sidebands)"), ("FLTF", "Band-pass window bottom"), ("FLTW", "Window width (127 open)"), ("LEV", "Level")])],
     [("BD MODERN", "SWEP pitch sweep · SMOD square mod · TMOD triangle mod · MENV mod length"),
      ("SD BASIC", "SWEP · INHM drum → metal · MDFB tone → rattle · MENV"),
      ("SD VINTAGE", "SWEP · INHM · FCMP denser body · MENV"), ("CP VINTAGE", "SPCR hand spacing · BAL claps/body · BODY · BENV"),
      ("CY ALLOY", "SHIM · RADIO · MOD metallic FM · MENV"), ("PC CARBON", "SWEP · INHM · MOD · MENV")]),
    ("contour", "CONTOUR", "contour", "Wave terrain synthesis: a point orbits over a surface; the height under it is the sound.",
     "SURF SINE with small SIZX/SIZY is a clean tone. Open the sizes for brightness, move CNTX/CNTY to find a spot, then try SURF and RATIO.",
     [("SYN1 Orbit", [("TUNE", "Pitch (64 the note)"), ("RATIO", "Y:X speed: circles to Lissajous"), ("SIZX", "Orbit width: sine → whole terrain"),
                      ("SIZY", "Orbit height"), ("CNTX", "Where it sits, left ↔ right"), ("CNTY", "Where it sits, down ↔ up"),
                      ("ROT", "Turns the orbit"), ("DRFT", "Centre wanders: held notes evolve")]),
      ("SYN2 Land", [("SURF", "SINE FOLD CHEB FM RING EDGE CHAOS BITS"), ("MORPH", "Bends the surface"), ("WARP", "Distorts the orbit before reading"),
                     ("FOLD", "Wavefolder after"), ("FM", "Output speeds the orbit: growl"), ("FDBK", "Output pushes the orbit: thickens, snarls"),
                     ("GRIT", "Sample and bit crush"), ("LEV", "Level")])],
     [("A clean tone", "SURF SINE, SIZX and SIZY small"), ("Brighter", "open SIZX and SIZY: the orbit crosses more hills"),
      ("Held notes that move", "raise DRFT"), ("A snarl", "raise FM and FDBK")]),
]

SMEAR_PAGES = [("SYN1", [("TUNE", "Transposes PLAY (tape) and the grains"), ("SPD", "Read speed −4…+4; centre stops it"),
                         ("BLND", "PLAY ↔ GRN grains"), ("SAMP", "Sample or FLEX buffer B1-B8"), ("STRT", "Loop start: scan here"),
                         ("SIZE", "Loop length (fine when small)"), ("DENS", "Grains a second"), ("LEV", "Level")]),
               ("SYN2", [("OVLP", "Grain length"), ("SPRY", "Grains scattered round the read point"), ("PRND", "Random grain pitch"),
                         ("WIN", "Grain shape: GAUS BHAR EXPO TRI RAMP SINC RECT"), ("FRZ", "Freeze: hold the moment as grains"),
                         ("", ""), ("", ""), ("", "")])]

FLEX_PAGE = ("FLEX track", [("TUNE", "Pitch"), ("PLAY", "FWD, FWDL, REV, REVL"), ("", ""), ("BUF", "Which buffer B1-B8"),
                            ("STRT", "Start in the take"), ("LEN", "Length"), ("LOOP", "Loop point"), ("LEV", "Level")])
SETUP_PAGE = ("FLEX REC · REC SETUP", [("SRC", "TRK1-16, IN, MAIN, BUS"), ("CHAN", "L+R, L or R"), ("BUF", "Buffer it records into"),
                                             ("R.LEN", "Take length (FUNC: bars)"), ("ARM", "Recorder's own arming"), ("Q.REC", "Trigless: start on next boundary"),
                                             ("GAIN", "Take level (0 = source level)"), ("MUTE", "Silence the source while it plays")])

GLASS_PAGE = ("FLTR page with Glass", [("ATK", "Envelope attack"), ("DEC", "Envelope decay"), ("ABND", "Attack curve (on SUS)"), ("DBND", "Decay curve (on REL)"),
                                       ("FREQ", "Cutoff = the ringing pitch"), ("RES", "Ring time: ms to 4 s"), ("TYPE", "LP → BP → HP"),
                                       ("ENV", "Envelope on cutoff (middle none)")])
VERB = [("PRE", "Pre-delay, up to 0.3 s"), ("DEC", "A short room to a long plate"), ("FREQ", "Corner of the high shelf inside the tank"),
        ("GAIN", "How much brightness survives each pass (low: a dark tail)"), ("HPF, LPF, VOL", "Stock's, unchanged")]

TIPS = [("Any machine", "[TRK] + CLEAR ([FUNC] + [PLAY]) resets a RIFT machine to its own start sound."),
        ("Any machine", "Hold a trig to see its p-locks highlighted with their values."),
        ("Any machine", "Word controls move four detents a choice: they never glide, even under LFOs."),
        ("FASCIA", "[FUNC] + turn: TUNE jumps octaves; GEOM and SHIFT snap to 0."),
        ("CPU", "When the DSP is busy, the oldest tails drop first, never the newest note or a held chord."),
        ("CPU", "SILT's QUAL DEEP costs the most DSP time: use it on one or two tracks."),
        ("FLEX", "Record a CPU-heavy track into a buffer, play it from FLEX, mute the source (MUTE SRC)."),
        ("FLEX", "Any sample machine can play a buffer: turn SAMP past 127 to B1-B8."),
        ("FLEX", "A loud BUS or MAIN take can clip: turn GAIN down."),
        ("SMEAR", "An LFO on SPD, STRT or BLND gives it motion: STRT scans, BLND moves between tape and cloud."),
        ("SMEAR", "p-lock FRZ ON on single trigs for frozen stutters."),
        ("Slides", "TRIG page 2: SLD on, SLEN sets the time; SLEN NXT glides until the next trig."),
        ("Direct Jump", "[PTN] + [YES] on: a pattern cued with [PTN] + [TRIG] starts at once, from the same position. [PTN] + [NO] off."),
        ("Keyboard", "[PTN] + [KEYBOARD]: KEYBOARD HOLD keeps notes on; again releases them."),
        ("Tuning", "KB SETUP's H is TUNE: turn it for the track's tuning, push it for the TUNING page. SLICE and GRID are never retuned."),
        ("GLASS", "Max RES + KEY.T up: GLASS becomes a playable resonator for short hits.")]


def cells(page) -> str:
    title, cs = page
    out = []
    for i, (p, d) in enumerate(cs):
        k = "ABCDEFGH"[i]
        if not p:
            out.append(f'<div class="cell empty"><span class="k">{k}</span></div>')
        else:
            out.append(f'<div class="cell" data-s="{E((p + " " + d).lower())}"><span class="k">{k}</span>'
                       f'<b>{E(p)}</b><span class="d">{E(d)}</span></div>')
    return f'<figure class="screen"><figcaption>{E(title)}</figcaption><div class="grid">{"".join(out)}</div></figure>'


def recipes(rs) -> str:
    return '<ul class="rec">' + "".join(f'<li data-s="{E((a + " " + b).lower())}"><b>{E(a)}</b><span>{E(b)}</span></li>' for a, b in rs) + "</ul>"


def machine(m) -> str:
    mid, name, lg, line, quick, pages, recs = m
    return (f'<section class="mach" id="{mid}"><header><div class="logo">{logo(lg)}</div><div><h2>{name}</h2><p class="line">{E(line)}</p></div></header>'
            f'<p class="quick"><span class="tag">Fastest sound</span>{E(quick)}</p>'
            f'<div class="pages">{"".join(cells(p) for p in pages)}</div>{recipes(recs)}</section>')


KEY = lambda s: "".join(f'<kbd>{E(k)}</kbd>' if i % 2 == 0 else f'<i>{E(k)}</i>' for i, k in enumerate(s.split("|")))

FLEX_STEPS = [
    ("Put FLEX on a track", "[FUNC]|+|[SYN]", "MACHINE SEL → FLEX. Its trig length becomes INF so you hear whole takes. BUF picks the buffer it plays."),
    ("Open FLEX REC", "[FUNC]|+|[VOICE]", "On the FLEX track. LEFT / RIGHT: REC TRIGS ↔ REC SETUP ↔ REC BUS."),
    ("Choose what to record", "REC SETUP", "SRC: a track (TRK1-16), IN, MAIN or BUS. R.LEN: how many steps. BUF: which buffer."),
    ("Place recorder trigs", "[TRIG]|or|[FUNC]|+|[TRIG]", "On REC TRIGS: [TRIG] a one-shot (records once), [FUNC] + [TRIG] every pass. [PAGE] for more steps."),
    ("Play and listen", "[PLAY]", "The take records on its step. A FLEX note trig on that step plays it as it arrives."),
]
FLEX_MORE = [("Record now, no trigs", "[YES] while playing: Q.REC waits for the next boundary, then records R.LEN steps. [NO] cancels."),
             ("Re-arm one-shots", "[YES] [YES]"), ("Keep a take", "[FUNC] + [YES]: next empty sample slot, onto the +Drive."),
             ("Clear a buffer", "[FUNC] + [NO] on REC SETUP, then [YES]."), ("Free the CPU", "MUTE SRC ON: the source is silent while the take plays.")]


def flex() -> str:
    steps = "".join(f'<li data-s="{E((t + " " + d).lower())}"><div class="n">{i + 1}</div><div><h4>{E(t)}</h4><div class="keys">{KEY(k)}</div>'
                    f'<p>{E(d)}</p></div></li>' for i, (t, k, d) in enumerate(FLEX_STEPS))
    more = "".join(f'<li data-s="{E((a + " " + b).lower())}"><b>{E(a)}</b><span>{E(b)}</span></li>' for a, b in FLEX_MORE)
    return f"""<section class="mach" id="flex"><header><div class="logo">{logo("flex")}</div><div><h2>FLEX: record and play back live</h2>
<p class="line">Eight buffers (B1-B8). Record a track, the input, the whole mix or a bus of tracks, in time, then play it like a sample.</p></div></header>
<div class="pipe">
<div class="pb"><b>SOURCE</b><span>TRK1-16 \u00b7 IN \u00b7 MAIN \u00b7 BUS</span></div><div class="pa" aria-hidden="true"></div>
<div class="pb"><b>REC TRIG</b><span class="trigs"><i class="sw on"></i><i class="sw hatch"></i><i class="sw"></i><i class="sw"></i><i class="sw"></i></span></div><div class="pa" aria-hidden="true"></div>
<div class="pb"><b>BUFFER B1-B8</b><svg viewBox="0 0 110 22" width="110" height="22" aria-hidden="true"><path class="wave" d="M2 11 l5 -7 l5 14 l5 -17 l5 20 l5 -11 l5 6 l5 -12 l5 15 l5 -9 l5 5 l5 -7 l5 9 l5 -4 l5 3 l5 -2 l5 1 l5 -1 l5 0 l5 0 l5 0"/></svg></div><div class="pa" aria-hidden="true"></div>
<div class="pb"><b>FLEX TRACK</b><span>a note trig plays it</span></div>
</div>
<ol class="steps">{steps}</ol>
<div class="cols">{cells(SETUP_PAGE)}{cells(FLEX_PAGE)}</div>
<ul class="rec">{more}</ul>
<p class="legend"><span class="sw on"></span>recorder trig (every pass) <span class="sw hatch"></span>one-shot <span class="sw spent"></span>spent one-shot</p>
</section>"""


def smear() -> str:
    return f"""<section class="mach" id="smear"><header><div class="logo">{logo("smear")}</div><div><h2>SMEAR: granular looper</h2>
<p class="line">One loop of a sample (or a FLEX buffer), read two ways: PLAY like tape, GRN as a cloud of grains. BLND mixes them.</p></div></header>
<div class="flow sm"><svg viewBox="0 0 520 210" role="img" aria-label="A sample with its loop, the read point and grains">
<rect x="1" y="1" width="518" height="208" rx="12" class="panel"/>
<path class="wave dim" d="{wave_path(20, 112, 480, 56, 3)}"/>
<rect x="150" y="56" width="220" height="112" class="loop"/>
<path class="wave" d="{wave_path(150, 112, 220, 56, 3, start=130)}"/>
<path d="M150 176V186H370V176" class="br"/><text x="260" y="203" class="lab">SIZE: loop length</text>
<text x="144" y="190" class="lab" text-anchor="end">STRT</text>
<line x1="230" y1="56" x2="230" y2="168" class="head"/><path d="M230 54l-6 -9h12z" class="headtip"/><text x="244" y="34" class="lab" text-anchor="start">read point, moved by SPD</text>
{grains()}
</svg>
<ul class="vl side">
<li><b><span class="dot g"></span>Grains</b><span>DENS how many \u00b7 OVLP how long \u00b7 SPRY how scattered \u00b7 PRND detune \u00b7 WIN shape</span></li>
<li><b><span class="blnd"><i></i></span>BLND</b><span>0: PLAY (tape) \u2192 127: GRN (grains)</span></li>
<li><b><span class="dot f"></span>FRZ</b><span>Holds the read point; PLAY's share turns into grains</span></li>
</ul></div>
<ol class="steps">
<li data-s="load sample samp"><div class="n">1</div><div><h4>Load a sample</h4><div class="keys"><kbd>SAMP</kbd></div><p>Turn SAMP: the sample list opens. [YES] keeps it. Past 127 are the FLEX buffers.</p></div></li>
<li data-s="play tape tune blnd"><div class="n">2</div><div><h4>Play it as tape</h4><div class="keys"><kbd>BLND 0</kbd></div><p>Notes and TUNE transpose it. SPD changes speed (and pitch); its centre stops the read point.</p></div></li>
<li data-s="loop strt size scan"><div class="n">3</div><div><h4>Pick the loop</h4><div class="keys"><kbd>STRT</kbd><kbd>SIZE</kbd></div><p>Small SIZE loops a tiny piece. Move STRT, or put an LFO on it, to scan.</p></div></li>
<li data-s="grains cloud dens ovlp spry"><div class="n">4</div><div><h4>Turn it into grains</h4><div class="keys"><kbd>BLND → 127</kbd></div><p>DENS for more grains, OVLP for longer ones, SPRY to scatter, PRND to detune, WIN to shape.</p></div></li>
<li data-s="freeze frz hold"><div class="n">5</div><div><h4>Freeze the moment</h4><div class="keys"><kbd>FRZ ON</kbd></div><p>Page 2, knob E. The read point holds and keeps sounding as grains while you play over it.</p></div></li>
</ol>
<div class="cols">{"".join(cells(p) for p in SMEAR_PAGES)}</div>
<p class="note">The phase vocoder (VOC) is switched off for now: BLND's VOC end plays PLAY. It returns once it fits the DSP.</p>
</section>"""


def wave_path(x0, cy, w, amp, step, start=0) -> str:
    import math
    pts = []
    for i in range(0, w + 1, step):
        t = (i + start) / 18.0
        a = amp * (0.35 + 0.65 * abs(math.sin(t / 7.3))) * (0.55 + 0.45 * math.sin(t * 1.7))
        pts.append(f"{x0 + i},{cy + (a if (i // step) % 2 else -a) * 0.5:.1f}")
    return "M" + " L".join(pts)


def grains() -> str:
    import random
    r = random.Random(7)
    out = []
    for _ in range(18):
        x = 230 + r.gauss(0, 30)
        y = 112 + r.gauss(0, 24)
        out.append(f'<ellipse cx="{x:.0f}" cy="{y:.0f}" rx="{r.uniform(5, 10):.0f}" ry="4" class="grain"/>')
    return "".join(out)


def fx() -> str:
    return f"""<section class="mach" id="fx"><header><div class="logo glyph"><svg viewBox="0 0 46 32" width="92" height="64"><path d="M2 26C10 26 12 4 23 4S36 26 44 26" fill="none" stroke="currentColor" stroke-width="2"/><path d="M14 16c3 -4 6 -4 9 0s6 4 9 0" fill="none" stroke="currentColor"/></svg></div><div><h2>GLASS filter and the plate</h2>
<p class="line">GLASS: a ringing filter on any machine's FLTR page (pick Glass after Equalizer). The master REVERB is a plate now.</p></div></header>
<p class="quick"><span class="tag">Fastest sound</span>GLASS: raise RES, set FREQ to the pitch you want it to ring at, hit it with short sounds. KEY.T up: the ring follows the notes. Page 2's LPG (from 64): a bongo-like ping.</p>
<div class="cols">{cells(GLASS_PAGE)}<figure class="screen"><figcaption>FX \u00b7 REVERB: a stereo plate (same page, same knobs)</figcaption><ul class="vl">{"".join(f'<li data-s="{E((a + " " + b + " reverb plate").lower())}"><b>{E(a)}</b><span>{E(b)}</span></li>' for a, b in VERB)}</ul></figure></div>
<ul class="rec"><li data-s="lpg glass gate"><b>LPG</b><span>Page 2, in ENV DELAY's place: from 64, level and cutoff open on each trig and close like a vactrol (DEC sets how long).</span></li>
<li data-s="key.t glass"><b>KEY.T</b><span>How far the cutoff follows the note.</span></li></ul></section>"""


def tips() -> str:
    return '<section id="tips"><h2>Tips</h2><div class="tips">' + "".join(
        f'<div class="tip" data-s="{E((a + " " + b).lower())}"><span class="tag">{E(a)}</span><p>{E(b)}</p></div>' for a, b in TIPS) + "</div></section>"


def build() -> str:
    nav = [("flex", "FLEX"), ("smear", "SMEAR")] + [(m[0], m[1]) for m in MACHINES] + [("fx", "GLASS + plate"), ("tips", "Tips")]
    tiles = "".join(f'<a class="tile" href="#{i}">{logo(lg) if lg else ""}<span>{n}</span></a>' for i, n, lg in
                    [("flex", "FLEX", "flex"), ("smear", "SMEAR", "smear")] + [(m[0], m[1], m[2]) for m in MACHINES])
    body = "".join([flex(), smear()] + [machine(m) for m in MACHINES] + [fx(), tips()])
    return PAGE.replace("@VER@", E(COVERS)).replace("@NAV@", "".join(f'<a href="#{i}">{E(n)}</a>' for i, n in nav)).replace("@TILES@", tiles).replace("@BODY@", body)


PAGE = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RIFT quick guide</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;700&family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet">
<style>
/* VOICE everyday reference for players at the instrument
   IDEA the Digitone's own screen: every page drawn as its eight knob cells, A-D over E-H
   PICTURE the machines' MACHINE SEL logos as a row of pixel tiles, then each machine's pages
   COLOUR the manual's night ground, OLED black screens, mint for what you press
   TYPE Space Grotesk + JetBrains Mono for the instrument's words
   LAYOUT laptop: tiles band, then sections with screens two across; phone: one column */
:root{color-scheme:dark;--bg:#0a0b0c;--panel:#141518;--scr:#000;--line:#2c2f34;--ink:#ecebe7;--dim:#9a9da3;--acc:#5fe3b0;--hot:#ffb86b}
*{box-sizing:border-box;min-width:0}
html{scroll-padding-top:64px}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 'Space Grotesk',system-ui,sans-serif;overflow-x:clip}
a{color:var(--acc)}
.wrap{max-width:1180px;margin:0 auto;padding:0 max(16px,3vw)}
.top{padding:28px 0 8px}
h1{font-size:clamp(32px,5vw,48px);line-height:1.05;margin:0 0 6px;letter-spacing:-.02em}
.sub{color:var(--dim);margin:0 0 18px;max-width:62ch}
.sub a{white-space:nowrap}
.tiles{display:grid;grid-template-columns:repeat(auto-fill,minmax(118px,1fr));gap:10px;margin:8px 0 18px}
.tile{display:flex;flex-direction:column;align-items:center;gap:8px;background:var(--scr);border:1px solid var(--line);border-radius:12px;padding:14px 8px 10px;text-decoration:none;color:var(--ink);font:700 13px 'JetBrains Mono',monospace;transition:border-color .15s}
.tile:hover,.tile:focus-visible{border-color:var(--acc)}
.px{image-rendering:pixelated;width:92px;height:64px;filter:drop-shadow(0 0 6px rgba(95,227,176,.25))}
.find{position:sticky;top:0;z-index:5;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 0}
.find .wrap{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.find input{flex:1 1 260px;font:16px 'JetBrains Mono',monospace;background:var(--panel);color:var(--ink);border:1px solid var(--line);border-radius:10px;padding:10px 12px;min-height:44px}
.find input:focus{outline:2px solid var(--acc);outline-offset:1px}
.find nav{display:flex;flex-wrap:wrap;gap:4px 12px;font-size:14px}
.find nav a{text-decoration:none}
.mach,#tips{padding:34px 0 10px;border-bottom:1px solid var(--line)}
.mach header{display:flex;gap:16px;align-items:center;margin-bottom:14px}
.logo{flex:none;background:var(--scr);border:1px solid var(--line);border-radius:12px;padding:8px;display:grid;place-items:center;color:var(--acc)}
h2{font-size:clamp(24px,3vw,32px);line-height:1.05;margin:0 0 4px;letter-spacing:-.01em}
.line{margin:0;color:var(--dim);max-width:70ch}
.quick{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px 14px;margin:0 0 14px}
.tag{display:inline-block;font:700 12px 'JetBrains Mono',monospace;color:#0a0b0c;background:var(--acc);border-radius:6px;padding:2px 7px;margin-right:9px}
.pages,.cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,520px),1fr));gap:14px}
.screen{margin:0;background:var(--scr);border:1px solid var(--line);border-radius:12px;padding:10px 10px 12px}
.screen figcaption{font:700 12px 'JetBrains Mono',monospace;color:var(--dim);margin:0 2px 8px}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}
.cell{position:relative;border:1px solid #23262a;border-radius:8px;padding:8px 8px 9px;min-height:84px;background:#07080a}
.cell .k{position:absolute;top:5px;right:7px;font:11px 'JetBrains Mono',monospace;color:#5b5f66}
.cell b{display:block;font:700 15px 'JetBrains Mono',monospace;color:var(--acc);letter-spacing:.02em}
.cell .d{display:block;font-size:13px;line-height:1.3;margin-top:3px;color:#d9dad6}
.cell.empty{background:transparent;border-style:dashed}
.cell.hit{border-color:var(--hot);box-shadow:0 0 0 1px var(--hot) inset}
.rec{list-style:none;padding:0;margin:14px 0 0;display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,300px),1fr));gap:8px}
.rec li{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:9px 12px}
.rec b{display:block;font-size:14px}.rec span{font:13px/1.4 'JetBrains Mono',monospace;color:#cfd0cc}
.flow{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:10px;margin:0 0 14px;overflow-x:auto}
.flow svg{display:block;width:100%;min-width:560px;height:auto}
.st rect{fill:#000;stroke:var(--line)}
svg text{fill:var(--ink);font:700 14px 'JetBrains Mono',monospace;text-anchor:middle}
svg text.s{font-weight:400;font-size:12px;fill:var(--dim)}
.arr{stroke:var(--acc);stroke-width:2;fill:none}
.trig rect{fill:none;stroke:var(--ink)}.trig .on{fill:var(--ink)}.trig .hatch{fill:url(#h)}
.wave{fill:none;stroke:var(--acc);stroke-width:1.6}.wave.dim{stroke:#3a3e44}
.panel{fill:#000;stroke:var(--line)}
.loop{fill:rgba(95,227,176,.07);stroke:none}
.br{fill:none;stroke:var(--dim)}
.lab{font-weight:400;font-size:13px;fill:var(--dim)}
.head{stroke:var(--hot);stroke-width:2}.headtip{fill:var(--hot)}
.grain{fill:rgba(255,184,107,.28);stroke:var(--hot);stroke-width:.8}
.track{fill:#23262a}.knob{fill:var(--acc)}
.frz{fill:none;stroke:#9fd8ff;stroke-width:2}.frzx{stroke:#9fd8ff;stroke-width:2}
.steps{list-style:none;counter-reset:s;padding:0;margin:0 0 14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,210px),1fr));gap:10px}
.steps li{display:flex;gap:10px;background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}
.steps .n{flex:none;width:30px;height:30px;border-radius:50%;background:var(--acc);color:#0a0b0c;font:700 15px 'JetBrains Mono',monospace;display:grid;place-items:center}
.steps h4{margin:2px 0 6px;font-size:16px}.steps p{margin:6px 0 0;font-size:14px;color:#d3d4cf}
.keys{display:flex;flex-wrap:wrap;gap:4px;align-items:center}
kbd{font:700 12px 'JetBrains Mono',monospace;background:#1e2024;border:1px solid #3a3e44;border-bottom-width:3px;border-radius:6px;padding:3px 7px;color:var(--ink);white-space:nowrap}
.keys i{font-style:normal;color:var(--dim);font-size:13px}
.legend{font-size:13px;color:var(--dim);display:flex;flex-wrap:wrap;gap:6px 14px;align-items:center}
.sw{display:inline-block;width:12px;height:12px;border:1px solid var(--ink);vertical-align:-2px;margin-right:4px}
.sw.on{background:var(--ink)}.sw.hatch{background:repeating-linear-gradient(45deg,var(--ink) 0 2px,transparent 2px 4px)}
.sw.spent{background:linear-gradient(45deg,transparent 45%,var(--ink) 45% 55%,transparent 55%)}
.note{font-size:14px;color:var(--dim);border-left:3px solid var(--hot);padding:2px 0 2px 10px}
.tips{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,270px),1fr));gap:10px;margin-top:12px}
.tip{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:12px}.tip p{margin:8px 0 0;font-size:14px}
.pipe{display:flex;flex-wrap:wrap;align-items:stretch;gap:8px;margin:0 0 14px}
.pb{flex:1 1 150px;background:var(--scr);border:1px solid var(--line);border-radius:12px;padding:12px;display:flex;flex-direction:column;gap:6px;align-items:center;justify-content:center;text-align:center}
.pb b{font:700 14px 'JetBrains Mono',monospace}.pb span{font:12px 'JetBrains Mono',monospace;color:var(--dim)}
.pb .trigs{display:flex;gap:4px}.pb .trigs .sw{margin:0}
.pa{flex:0 0 22px;align-self:center;height:2px;background:var(--acc);position:relative}
.pa::after{content:"";position:absolute;right:-1px;top:-5px;border:6px solid transparent;border-left:8px solid var(--acc);border-right:0}
.flow.sm{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:14px;align-items:center;overflow:visible}
.flow.sm svg{min-width:0}
.vl{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.vl li{display:grid;gap:2px}.vl b{font:700 14px 'JetBrains Mono',monospace;color:var(--acc);display:flex;align-items:center;gap:8px}.vl span{font-size:14px;color:#d3d4cf}
.screen .vl{padding:4px 4px 0}
.dot{display:inline-block;width:14px;height:10px;border-radius:50%}.dot.g{background:rgba(255,184,107,.35);border:1px solid var(--hot)}.dot.f{border:2px solid #9fd8ff;width:12px;height:12px}
.blnd{display:inline-block;width:34px;height:8px;border-radius:4px;background:#23262a;position:relative}.blnd i{position:absolute;right:4px;top:-3px;width:14px;height:14px;border-radius:50%;background:var(--acc)}
@media(max-width:700px){.flow.sm{grid-template-columns:minmax(0,1fr)}.pipe{flex-direction:column}.pb{flex:none}.pa{flex:none;height:14px;width:2px;margin:0 auto}.pa::after{right:-5px;top:auto;bottom:-2px;border:6px solid transparent;border-top:8px solid var(--acc);border-bottom:0}}
.gone{display:none!important}
.foot{color:var(--dim);font-size:13px;padding:24px 0 48px}
@media(max-width:600px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.mach header{align-items:flex-start}.px{width:69px;height:48px}}
@media(prefers-reduced-motion:reduce){.tile{transition:none}}
</style></head><body>
<svg width="0" height="0" style="position:absolute"><defs><pattern id="h" width="4" height="4" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><rect width="2" height="4" fill="#ecebe7"/></pattern></defs></svg>
<div class="wrap top">
<h1>RIFT quick guide</h1>
<p class="sub">Every RIFT machine's controls at a glance, laid out as the Digitone's pages: knobs A-D on top, E-H below. RIFT v@VER@. The full story is in the <a href="rift-manual.html">manual</a>.</p>
<div class="tiles">@TILES@</div>
</div>
<div class="find"><div class="wrap"><input id="q" type="search" placeholder="Find a control or tip: FRZ, DAMP, R.LEN, bow…" aria-label="Find a control or tip" autocomplete="off"><nav>@NAV@</nav></div></div>
<main class="wrap">@BODY@
<p class="foot">Everything else (p-locks, LFOs, kits, MIDI) works as on the stock Digitone II. Unofficial: not made or supported by Elektron. <a href="rift-manual.html">Full manual</a>.</p>
</main>
<script>
{
const q=document.getElementById('q');
const items=[...document.querySelectorAll('[data-s]')];
const secs=[...document.querySelectorAll('main section')];
const run=()=>{const v=q.value.trim().toLowerCase();
for(const el of items){const hit=!!v&&el.dataset.s.includes(v);el.classList.toggle('hit',hit);}
for(const s of secs){if(!v){s.classList.remove('gone');continue;}
const any=[...s.querySelectorAll('[data-s]')].some(e=>e.dataset.s.includes(v))||s.querySelector('h2').textContent.toLowerCase().includes(v);
s.classList.toggle('gone',!any);}};
q.addEventListener('input',run);
}
</script>
</body></html>
"""


def main(argv=None) -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=str(ROOT / "site" / "rift-quick.html"))
    o = a.parse_args(argv)
    pathlib.Path(o.out).write_text(build(), encoding="utf-8")
    print(f"wrote {o.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
