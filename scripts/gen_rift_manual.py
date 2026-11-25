#!/usr/bin/env python3
"""Writes site/rift-manual.html: RIFT's manual (the patcher's MANUAL button and its "What's new").

The control tables come from each machine's own module (names, pages, choices, start values), so
they can never disagree with the firmware; the prose is here. A machine whose module this tree
does not have (THOLET before v0.15) is left out, and so is its version entry.

    python3 scripts/gen_rift_manual.py [--out site/rift-manual.html]

Owner, 2026-11-20: "update the manual for every new feature and go in depth with the machines,
especially each control and especially ligature and what each block does/how to use it".
"""
from __future__ import annotations

import argparse
import html
import importlib
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def E(s: str) -> str:
    return html.escape(s, quote=False)


def have(mod: str) -> bool:
    try:
        importlib.import_module(mod)
        return True
    except ImportError:
        return False


HAS_THOLET = False                      # v0.22 (owner: "it still mentions tholet"): THOLET (v0.15..v0.16) is gone from the manual
HAS_PLATEAU = have("dnfw.plateau.machines")      # RIFT v0.17: the first FX machine
HAS_GLASS = have("dnfw.glass.live")              # RIFT v0.18: the FLTR type GLASS
HAS_CONTOUR = have("dnfw.contour.machines")      # RIFT v0.19: wave terrain
HAS_SPALL = have("dnfw.spall.machines")          # RIFT v0.25: particles


def has_smear() -> bool:
    try:
        from dnfw.sampler import machines as SM
        return hasattr(SM, "SMEAR_RECORDS")
    except ImportError:
        return False


HAS_SMEAR = has_smear()

# --------------------------------------------------------------------------------------------
# What each control does. Keys are the panel's names; text is plain (escaped) except <b>/<i>
# written here on purpose (kept as markup: R() marks a string as raw).
# --------------------------------------------------------------------------------------------


class R(str):
    """raw markup"""


FASCIA = {
    "TYPA": "Exciter A: what sets the bodies moving. STRIKE is a mallet (a short pulse; HARD makes it narrower and brighter). BLOW is a reed driven by breath against the body (HARD brightens the turbulence). BOW is a friction bow computed every sample (HARD is bow pressure, airy to scraping; DEC keeps the bow on). DUST is sparse random impulses (their density is DUST). PULSE is a sine burst with a pitch drop set by BEND. TZFM is through-zero FM (SIDE sets the modulator ratio).",
    "TYPB": "Exciter B: a second exciter of the same six types, mixed with A by MIX. Use two different types for hybrids: STRIKE + BOW for a bowed vibe with a mallet attack, BLOW + DUST for a breathy rattle.",
    "HARD": "Hardness: mallet hardness for STRIKE (soft felt at 0, a hard tip at 127), bow pressure for BOW, turbulence brightness for BLOW. Velocity scales it too. Also sets how loud CLIK's transient is.",
    "DUST": "Dust: contact noise and grit. Random micro-impacts on STRIKE, rosin grit (random catches) on BOW, and the impulse density of the DUST exciter.",
    "TZFM": "Thru-zero FM: on the TZFM exciter, the FM index (the phase can run backwards: metallic, then clangorous). On any other exciter, a short TZFM burst at the attack, for a bright metallic edge on a strike.",
    "BEND": "Bend: a pitch glide that follows the body's own level, up to 7 semitones at full: the tension glide of a struck drum skin. Hard hits also add a 4 ms contact chirp. On PULSE it is the burst's pitch drop.",
    "MIX": "Exciter mix: A only at 0, B only at 127, both between.",
    "DEC": "Exciter decay: how long the exciter keeps exciting. Short for a strike, long for a bow or breath that keeps the body singing.",
    "BODA": "Body A, the main resonator (16 modes). MEMB a drum skin (Bessel ratios), PLATE a metal plate, BAR a free bar (marimba-like), VIBE a tuned vibraphone bar, CHIME a tubular chime (struck note in tune), BELL measured bell ratios, GLASS a wine glass, TUBE odd harmonics (closed pipe, clarinet-like), STRING plain harmonics.",
    "BODB": "Body B, a second resonator of the same types, or OFF. Its pitch is fixed by its type against Body A (TUBE and STRING 1:1, MEMB and CHIME 3:2, GLASS 4:3, PLATE, VIBE and BELL 2:1, BAR 2.756), so pairs are always in a musical relation. How B hears A is XMOD and COUP.",
    "TUNE": "Tune: the bodies' pitch around the note, in semitones (bipolar; 64 is the note). FUNC + turn jumps by octaves (0, 32, 64, 96, 127).",
    "GEOM": "Geometry: stretches or squeezes the mode ratios (ratio to the power 0.6 .. 1.4): left is more harmonic and woody, right more inharmonic and metallic. 64 is the body as measured. FUNC + turn snaps to the centre.",
    "MATL": "Material: how fast the high modes die against the low ones. Low: wood or skin, the highs fade fast. High: metal and glass, the highs ring as long as the fundamental.",
    "POS": "Position: where the body is struck, edge to middle. Each mode is weighted by how much it moves there, so POS sweeps the overtone balance (a hollow centre hit to a bright edge hit).",
    "COUP": "Coupling: how much of Body A goes into Body B, in the way XMOD chooses.",
    "DAMP": "Damping: how long the bodies ring (the T60 of every mode). Low rings long (FASCIA starts at 28, about 3 s), high is a dead, short thud.",
    "MORPH": "Morph: moves each mode's level up the spectrum as the note rings, keeping the total level, so the timbre brightens or darkens over the tail without moving the pitch.",
    "FORM": "Formant: two vowel formants across a e i o u, after the bodies. Sweep it slowly or with an LFO for talking bells.",
    "SHIFT": "Frequency shift: a single-sideband shift of up to +-2000 Hz, bipolar around 64 (0 Hz). Small amounts give slow phasing beats; large amounts make any body inharmonic and alien. FUNC + turn snaps to 0.",
    "RING": "Ring mod: Body A times Body B, or times a sine at 1.414 x the note when Body B is OFF.",
    "SIDE": "Sideband: the TZFM modulator's ratio (0.5 to 7): sets which sidebands TZFM makes.",
    "FOLD": "Fold: a sine wavefolder on the output. Gentle at first, then rich and buzzy.",
    "LPG": "Low-pass gate: a contour that closes as the note dies, both darkening (it damps the high modes) and quietening it, the classic plucked/bongo decay.",
    "CHAR": "Character: an asymmetric saturation (warmth, then grit). FASCIA starts at 127.",
    "ATK": "Attack: the onset. On strikes it smears the hit over a rising window (a swell); on BOW and BLOW it is the rise time of the pressure. 0 is instant.",
    "CLIK": "Click: a transient straight to the output, of the type CTYP picks, scaled by HARD. Adds stick, tick or thump definition without changing the body.",
    "CTYP": "Click type: SNAP a band-limited crack, TICK a 1 ms high blip, NOISE a short bright burst, THUMP a 40 Hz knock with a falling pitch.",
    "XMOD": "Cross mod: how Body A acts on Body B. EXCITE: B is also struck by A's sound (COUP of it). BEND: A's level bends B's pitch, up to an octave. CHOKE: A ringing shortens B. TRADE: energy flows both ways (B back into A, A damped by what it gives).",
    "FDBK": "Feedback: Body B back into Body A, softly limited. Low amounts thicken and sustain; high amounts self-oscillate into howls.",
    "BUZZ": "Buzz: a contact gap on Body A. Where A swings past it, it buzzes (snare wires, a sitar's jawari, a rattle); the buzz also shakes Body B.",
    "WATR": "Water: the sound vocodes itself above the note: its upper partials heard through narrow detuned bands, gurgling like a water drum or a waterphone. The fundamental stays clean.",
    "VARY": "Variation: per-hit randomness (a little mode tuning and level each strike) and a slow drift of the modes while they ring. Brings repeated hits to life.",
}

ORGAN = {
    "STOP": "Stop: the pipe family, which sets every rank's tone. FLUTE (pure, hooty), NACHTHN (Nachthorn: a soft wide flute), PRINCPL (Principal: the classic church organ), GAMBA (a thin, string-like stop), TRUMPET (a reed, bright and brassy).",
    "R16": "The 16' rank: an octave below the note. Each R control is a drawbar: its level in the mix.",
    "R8": "The 8' rank: the note itself.",
    "R4": "The 4' rank: an octave above.",
    "R223": "Nazard (2 2/3'): the 12th, an octave and a fifth up. With 8' and 4', the hollow 'quint' colour.",
    "R2": "The 2' rank: two octaves up.",
    "R135": "Tierce (1 3/5'): the 17th, two octaves and a third up. With the Nazard, the reedy Cornet colour.",
    "R1": "The 1' rank: three octaves up. Sparkle on top.",
    "CHIFF": "Chiff: the breathy 'puff' at the start of each pipe's speech. 0 is a clean onset.",
    "SPEECH": "Speech: how slowly each pipe comes up to pitch and level. Low is immediate; high lets each note bloom.",
    "SPREAD": "Spread: detunes the ranks slightly against each other, a large organ's natural chorus.",
    "AIR": "Air: the noise of wind in the pipes, under the tone.",
    "WIND": "Wind: the wind supply's instability, a slight unsteady wobble of pitch and level, as a real bellows.",
    "TREM": "Tremulant: depth of the organ's tremulant (a pulsing of the wind).",
    "TRATE": "Tremulant rate.",
    "CELESTE": "Celeste: adds a slightly sharp extra rank (the Voix Celeste) that beats against the rest, a slow shimmering chorus. Fades in and out smoothly.",
    "PERC": "Percussion: a Hammond-style sine ping on the 2nd harmonic at each strike. 0 is off.",
    "PDEC": "Percussion decay: 40 ms to 1.5 s.",
    "MTUN": "Mixture tune: tunes the mixture's two pipes down 0..36 semitones (they sit at 6 and 16 times the note at 0).",
    "KCLK": "Key click: a 12 ms contact click at the strike.",
    "MCHR": "Mixture character: morphs the mixture's pipes toward the TRUMPET's tone (toward the FLUTE's on a TRUMPET stop).",
    "MIXT": "Mixture: the level of the mixture (high pipes at 6 and 16 times the note): a bright, glittering crown.",
    "ROTR": "Rotor: a rotating speaker's depth: level and tone swirl, plus Doppler on the pipes.",
    "RSPD": "Rotor speed, with a 0.7 s lag when it changes (the horn spinning up and down).",
    "BRTH": "Breath: the jet's turbulence inside the tone: level, pitch flutter and a darkening. Turns the organ into a played flute.",
    "TURB": "Turbulence: the breath's rate, 1.5 to 59 Hz.",
    "BREK": "Break: a downward voice-break, every other cycle changed, a component at half the pitch (overblown/underblown flute).",
    "BDEP": "Break depth: how strong the break is (up to 7 dB under the note).",
    "PRES": "Pressure: the blowing pressure: sharper, and more likely to break.",
    "BLOM": "Bloom: the pipe opens slowly from breath into tone (30 ms .. 3 s). With EDGE at 0 it is a pure swell.",
    "EDGE": "Edge: breath through the pipe, noise on a band-pass at the note. What you hear as BLOM opens.",
    "PVEL": "Pressure velocity: velocity on the pressure (harder notes blow harder).",
}

SILT = {
    "PART": "Partials: stiffness. FIBER: gut to wire (above 42 stiffer). SILT: grain size. SKIN: rubber to wood to wire. FLUID: stiffness, and which harmonics the drips fall on.",
    "TENS": "Tension. FIBER: brightness of the string's loop. SILT: the resonances' ratios. SKIN: elasticity, the size of the 'boing'. FLUID: surface tension, how far the pitch slumps as it melts.",
    "MASS": "Mass: body size (violin to bass on FIBER), heavier grains on SILT, slower settling on SKIN, a bigger ringing body on FLUID.",
    "COHE": "Cohesion: about 70 is natural; lower, the players come apart; higher, they lock together. On SILT, avalanches; on SKIN, the strands' coupling; on FLUID, drips falling in runs.",
    "VISC": "Viscosity: damping. Low on SKIN is a sharp pluck. On FLUID: water to honey (melt speed, drip size, darkness).",
    "GRAIN": "Grain: above 55 coarser grit and longer strokes (FIBER); grain duration (SILT); stroke and flutter length (SKIN); drip length (FLUID).",
    "DENS": "Density: above 32 crackle in SOLO, a cloud of extra players in MASS; the grain rate on SILT; flutter and re-strikes on SKIN; the drip rate on FLUID.",
    "BODY": "Body: the resonating body's amount on every material.",
    "PRESS": "Pressure: always 'how hard': bow force, a grain's weight, how far the rubber is pushed, how hard a drip falls. Feeds STRESS (see below).",
    "SPEED": "Speed: bow speed and rates; also sets GLISS, SWELL and melt time, TREMO's rate and LOOP FREE's rate.",
    "POS": "Position: edge to middle: the bow point, the strike point, the resonances' weights, the drips' harmonics.",
    "ROSIN": "Rosin: grip. On SILT, stickier grains avalanche more.",
    "SCRAP": "Scrape: irregular friction (compressed above its middle, so it stays musical).",
    "SNAP": "Snap: transient hardness; the overshoot on SKIN.",
    "AIR": "Air: breath noise, the air in the dust or the water.",
    "INST": "Instability: feeds STRESS, how near the matter is to failing.",
    "SPREAD": "Spread: the cluster's width; tunes the sympathetic strands in SOLO; detunes the resonances on SILT.",
    "VOICES": "Voices: how many players in MASS; sympathetic strands in SOLO; resonances on SILT.",
    "DRIFT": "Drift: each player's slow detuning.",
    "VIBR": "Vibrato, with an onset; COHE locks the players' phases.",
    "GLISS": "Glissando, centre zero. In the GLISS gesture, where the mass travels (+-12 semitones); in the others, a scoop into the note.",
    "FORM": "Formant: a band-pass that rises with the energy. Keep it low on FLUID (sweeping it there sounds like a phaser).",
    "ROUGH": "Roughness: collective friction; scatters the ensemble's strikes.",
    "MORPH": "Morph: tonal to particulate (pitch strength from full to about 14 %). Struck gestures splinter, bowed ones fragment.",
    "MAT": "Material: FIBER (strings), SILT (grains, sand, gravel), SKIN (rubber, membranes), FLUID (a molten body that drips and melts).",
    "GEST": "Gesture, what you do to the matter: BOW, SCRAPE, STACC (staccato), TREMO (tremolo), SPICC (spiccato, bounced), LEGNO (col legno, wood), GLISS (the mass travels, GLISS sets where), FRACT (fracture), SWELL (the players enter one by one), QUAKE (instability grows over the note).",
    "MODE": "Mode: SOLO (one player with sympathetic strands), MASS (an ensemble in pitch), MASS-8 (the ensemble an octave below, darker), SWARM (the material inside a particle cloud). In MASS modes velocity also decides how many players join (about 40 % softest, all at the hardest).",
    "DIST": "Distribution: the cluster's layout and how GLISS moves it. NARROW tight, together; WIDE in parallel at different speeds; BIMODAL two groups shearing apart; ASYM lopsided (GLISS right: a unison blooms into a cluster; left: a cluster collapses to a unison).",
    "LOOP": "Loop: restarts the gesture while the gate is open: OFF, every 16th, 8th or 4th, or FREE (SPEED sets the rate, SCRAP and ROUGH make it uneven).",
    "SHAPE": "Shape of the gesture's curves: SOFT, LINEAR, EXP (an accent: slow start, accelerating), CHAOTIC.",
    "TUNE": "Tuning of the players and strands: FREE, SCALE, MICRO, HARM (harmonic).",
    "QUAL": "Quality: ECO, NORMAL, DEEP (2, 4 or 8 filaments). DEEP costs the most DSP time; use it on one or two tracks.",
}

DIGIDRUM = {
    "TYPE": "Drum type: BD MODERN (kick), SD BASIC and SD VINTAGE (snares), CP VINTAGE (clap), CY ALLOY (cymbal), PC CARBON (percussion). Each has its own four controls in O1..O4. TYPE is p-lockable: one track can play a whole kit.",
    "TUNE": "Tune, in semitones (bipolar, 64 the type's own pitch).",
    "PNCH": "Punch: a fast accent envelope that also drives the sound: more snap and weight at the front.",
    "DEC": "Decay: the amp decay.",
    "O1": "Type control 1: named on the screen by the TYPE (see the table below).",
    "O2": "Type control 2 (see below).",
    "O3": "Type control 3 (see below).",
    "O4": "Type control 4 (see below).",
    "OVER": "Overdrive: a digital overdrive, from warm to crushed.",
    "EQF": "EQ frequency: where the EQ band sits.",
    "EQG": "EQ gain: boost or cut at EQF (64 flat).",
    "AMD": "AM depth: a tremolo (amplitude modulation) depth.",
    "AMF": "AM rate: the tremolo's speed; fast rates turn into AM sidebands.",
    "FLTF": "Filter base: the bottom of the band-pass window (high-pass from 0 up).",
    "FLTW": "Filter width: how wide the window is above FLTF (127 open).",
    "LEV": "Level.",
}
SPALL = {
    "TYPE": "The particle: IMP (one sharp impulse: a click), DUST (a burst of noise), TONE (a tiny grain of the six oscillators), CHIP (a hard, digital pulse: one oscillator's sign times the next's).",
    "SIZE": "How long each particle lasts, from 0.05 ms (a tick) to about 200 ms (a short tone).",
    "DENS": "How often particles are offered, from one every four seconds to about 500 a second. At 0 a trig makes one particle and nothing more.",
    "GAP": "The silence between: the chance an offered particle is skipped. Up, the texture gets sparser and more broken.",
    "EDGE": "Hard or soft: fully up each particle is a sharp edge; down it is rounded and soft, like contact noise.",
    "CLMP": "Clump: each particle that sounds is followed by up to seven more, fast, so particles land in little clusters with space around them.",
    "MEM": "Memory: at 0 every particle is new; up, after that many clock ticks the pattern starts again from where the note began, so a phrase of particles repeats exactly.",
    "LEV": "Level.",
    "TUNE": "Tune, in semitones (bipolar, 64 the note's own pitch): the oscillators' pitch.",
    "SPRD": "Spread: the six oscillators' tuning. At 0 a harmonic series; up, stretched and inharmonic, metallic.",
    "ALG": "How the oscillators make a TONE particle: SUM (all six together), RING (one times the next: ring modulation), SCAN (one oscillator a particle, the next particle the next).",
    "FRQA": "Resonator A's pitch, 30 Hz to 15 kHz. Every particle pings it.",
    "FRQB": "Resonator B's pitch.",
    "RING": "How long the resonators ring, from 5 ms to about 5 seconds.",
    "COUP": "Coupling: how much of A's ring feeds B, so the two ring as one stranger surface.",
    "MIX": "From the dry particles (0) to the resonators' rings (127).",
}
CONTOUR = {
    "TUNE": "Tune, in semitones (bipolar, 64 the note's own pitch).",
    "RATIO": "Y ratio: the speed of the orbit's Y motion against X, from a table of 16 (1:1 a circle or ellipse, others trace Lissajous figures; the uneven ratios never close and sound rougher).",
    "SIZX": "Size X: how wide the orbit is across the surface: from a near-sine at 0 to the whole terrain.",
    "SIZY": "Size Y: how tall the orbit is.",
    "CNTX": "Centre X: where on the surface the orbit sits, left to right (bipolar).",
    "CNTY": "Centre Y: where it sits, bottom to top (bipolar).",
    "ROT": "Rotation: turns the orbit on the surface.",
    "DRFT": "Drift: the orbit's centre wanders slowly over the surface, so the tone keeps changing on a held note.",
    "SURF": "Surface: the terrain the orbit reads: SINE, FOLD, CHEB (Chebyshev), FM, RING, EDGE, CHAOS, BITS.",
    "MORPH": "Morph: bends the surface's shape (each surface its own way).",
    "WARP": "Warp: distorts the orbit's coordinates before the surface is read.",
    "FOLD": "Fold: a wavefolder after the surface.",
    "FM": "FM: the output modulates the orbit's speed (through-zero-ish growl at the top).",
    "FDBK": "Feedback: the output pushes the orbit's position: a growl that thickens as it rises. Its original range (v0.26: v0.20's curve taken out); high settings turn wild on some surfaces and sizes, part of its character. Above B3 it follows the pitch, so high notes keep the low notes' character and stay in key.",
    "GRIT": "Grit: sample-and-bit crush.",
    "LEV": "Level.",
}
DIGIDRUM_OWN = {
    "SWEP": "Sweep: depth of the pitch sweep at the start.",
    "SMOD": "Square mod: a square-wave modulator on the kick, under the mod envelope: a hollow, gritty attack.",
    "TMOD": "Triangle mod: a triangle modulator, a softer FM body.",
    "MENV": "Mod envelope: how long the modulation lasts (and how strong it starts).",
    "INHM": "Inharmonic: pushes the overtones apart from the fundamental, from drum to metal.",
    "MDFB": "Mod feedback: FM feedback plus snare noise: from tone to rattle.",
    "FCMP": "Freq compress: squeezes the partials' levels together, a brighter, denser body.",
    "SPCR": "Spacing: the time between the clap's hands.",
    "BAL": "Balance: the claps against the body.",
    "BODY": "Body: the body's tone, from a soft thump to a ringing FM body.",
    "BENV": "Body envelope: the body's decay.",
    "SHIM": "Shimmer: the second metallic oscillator's ratio.",
    "RADIO": "Radio: the first oscillator's ratio, a broadcast-like metallic colour.",
    "MOD": "Modulation: the FM amount between the metallic oscillators.",
}

PLATEAU = {
    "PRED": "Pre-delay: the time before the reverb starts, up to half a second.",
    "SIZE": "Size of the plate: from a small, metallic space to a huge one.",
    "DCAY": "Decay: how long the tail lasts. HOLD on page 2 makes it endless.",
    "DIFF": "Diffusion: how smeared the reflections are. Low: you hear the echoes; high: a smooth wash.",
    "DAMP": "Damping: how fast the highs die in the tail (darker as it rises).",
    "BAND": "Input high cut: the brightness of what goes in.",
    "LCUT": "Input low cut: takes the low end out of what goes in.",
    "LEV": "Level of the reverb (the track's own LEVEL and AMP still apply).",
    "TLOW": "Tank low cut: takes the low end out of the tail itself (a lighter, less boomy decay).",
    "MSPD": "Modulation speed: how fast the tail's delays drift (chorus-like movement).",
    "MDEP": "Modulation depth: how far they drift.",
    "HOLD": "HOLD (OFF/ON): freezes the tail; the input closes and the decay is endless. Turn it off to let it fade.",
    "TUND": "TUNED (OFF/ON): the tank's loop length follows the note you play: the reverb becomes a resonator, ringing at the note's pitch.",
    "IGN": "Input gain: how hard the BUS drives the reverb (64 about unity).",
    "DRV": "Drive: a soft saturation inside the tank: warmer, and it keeps a HOLD or a loud BUS from building up.",
    "ERLY": "Early: mixes the diffused input (the first reflections) into the output.",
}

THOLET = {
    "TUNE": "Tune, in semitones (bipolar, 64 the note).",
    "HAMR": "Hammer: one of six Kawai grand hammer transients (DEEP, BRITE, SOFT, HIGH, MID, DARK), read at the note's pitch. The 'thock' that starts the note; BRTH sets how loud it is against the strings.",
    "TONE": "Tone: the strings' brightness (how strongly the upper partials are struck).",
    "FELT": "Felt: a felt layer between hammer and string (after Nils Frahm's felt piano): darker, softer, with a felt thud. 0 is no felt.",
    "DEC": "Decay: how long the strings ring while the note is held.",
    "EP": "Electric piano: morphs the strings toward a Rhodes tine (the bell-like first partials) and adds the pickup's bark. 0 is the grand, 127 a Rhodes.",
    "STRK": "String detune: two strings per note detuned against each other: 0 is pure, higher is the warm beating of a real (or old) piano.",
    "LEV": "Level.",
    "GRAN": "Grain amount: the grain cloud's level. The cloud swells in as the strings fade, so the note breaks up into grains in its tail. 0 is off.",
    "GDEN": "Grain density: grains a second.",
    "GSIZ": "Grain size: each grain's length.",
    "GFM": "Grain FM: a wobble of each grain's pitch, from still to warbling.",
    "GSPR": "Grain spread: how far back in the last third of a second the grains start: near the present (smeared) to far back (echoing fragments).",
    "REL": "Release: the damper. How fast the note dies after its key is let go (the note-off).",
    "VSNS": "Velocity sense: how much velocity changes level and brightness.",
    "BRTH": "Strike level: the hammer transient's level against the strings.",
}

SMEAR = [
    ("TUNE", "Tune", "Tune, in semitones (as every sample machine's). The note and TUNE set the pitch of every reader and never the speed, as on the Nebulae: PLAY and the grains both transpose while the read point keeps moving at SPD (v0.24; v0.22 and v0.23 played PLAY as tape)."),
    ("SPD", "Speed", "How fast the read point moves through the loop: -4.00 to +4.00 (64 is FRZ: the read point stops; +1.00 and -1.00 have wide detents). Negative reads backwards. Speed only: PLAY and the grains keep their pitch whatever the speed (v0.24)."),
    ("BLND", "Blend", "Crossfades the readers at constant power: VOC (the keyframe stretch, v0.26) at 0, PLAY (the read heads) in the middle, GRN (the grains) at 127."),
    ("SAMP", "Sample Slot", "The sample (or FLEX buffer B1..B8) SMEAR plays, as on every sample machine. Taken at the note."),
    ("STRT", "Start", "Where the loop starts in the sample."),
    ("SIZE", "Loop Size", "How long the loop is, from STRT toward the sample's end (squared, as on the Nebulae: fine control at small sizes)."),
    ("DENS", "Grain Density", "Grains a second, 0.12 to 2,500 (up to 10 at once)."),
    ("LEV", "Sample Level", "Level."),
    ("OVLP", "Grain Overlap", "Each grain's length against the density: short separate grains to long overlapping ones."),
    ("SPRY", "Grain Spray", "Scatters where each grain starts around the read point."),
    ("PRND", "Pitch Random", "Detunes each grain at random, up to +-120 cents."),
    ("WIN", "Grain Window", "The grains' envelope: GAUS (soft), BHAR (Blackman-Harris), EXPO (percussive), TRI, RAMP (reverse swell), SINC, RECT (hard-edged). Four detents a window, as every choice."),
    ("FRZ", "Freeze", "(v0.22) OFF / ON. ON holds the read point where it is, whatever SPD says, and hands PLAY's share of BLND to the grains, so the moment you froze keeps sounding as a grain cloud (DENS, OVLP, SPRY, PRND and WIN shape it). OFF: the read point moves on from there at SPD. p-lock it, or put it on an LFO, for stutters."),
]

# LIGATURE: the blocks (WEFT's), what they do, their two settings, what A and B do
BLOCKS = [
    ("PHASE", "PHAS", "Phase", "A ramp oscillator (a saw from -1 to +1) at the note's pitch times a ratio: the raw phase most voices start from. Feed it to WAVE to make a tone, or use it to drive another block.",
     "RATI: the ratio to the note (0.25, 0.5, 1, 1.5, 2, 2.5, 3, 4, 5, 6, 7, 8, 9, 11, 13, 16).", "TUNE: fine detune, +-1 semitone around 64.",
     "A: exponential FM on the rate (PHASE into PHASE: classic FM).", "B: hard sync: a rising edge on B resets the phase (sync leads)."),
    ("WAVE", "WAVE", "Wave", "A waveshaper oscillator. Free-running at the note, or, with A connected, a shaper that reads A as its phase. The shape morphs sine -> triangle -> saw -> square.",
     "SHAP: the shape (morphs between the four).", "WARP: bends the phase (pulse-width-like) around the middle.",
     "A: replaces the internal phase (connect a PHASE here for FM/PM and sync patches).", "B: phase modulation added to the phase (PM)."),
    ("SLOPE", "SLOP", "Slope", "An attack/decay envelope. Triggers on each note (or on a rising A), rises to the top at RISE, holds while the gate is held, then falls at FALL. The usual amp or filter envelope.",
     "RISE: the attack time (0.5 ms to about 8 s).", "FALL: the decay/release time.",
     "A: its own gate/trigger instead of the note (connect a CYCLE for a looping envelope).", "B: scales both times (positive = faster)."),
    ("CYCLE", "CYCL", "Cycle", "An LFO / slow oscillator, a triangle that can lean into a saw or a ramp.",
     "RATE: 0.02 Hz to audio rate.", "SKEW: the shape, ramp up <-> triangle <-> ramp down.",
     "A: exponential rate modulation.", "B: reset on a rising edge (sync it to the note's TRIG)."),
    ("SLEW", "SLEW", "Slew", "A lag (portamento) processor: follows A smoothly, with its own speed going up and going down. Smooth a stepped HOLD, make a GATE into a soft envelope, or glide pitch.",
     "RISE: time going up.", "FALL: time going down.",
     "A: the signal to follow.", "B: scales both times."),
    ("LP", "LP", "Low pass", "A resonant 12 dB state-variable low-pass filter.",
     "CUT: cutoff, 20 Hz to 18 kHz.", "RES: resonance, up to self-oscillation.",
     "A: the audio in.", "B: cutoff modulation (5 octaves): connect a SLOPE here for a filter envelope."),
    ("BP", "BP", "Band pass", "The same filter's band-pass output. Vowel-ish and nasal; with high RES, a ringing resonator you can strike with IMPULSE or noise.",
     "CUT: centre frequency.", "RES: resonance.",
     "A: the audio in.", "B: centre modulation."),
    ("HP", "HP", "High pass", "The filter's high-pass output: thins, removes rumble, or with RES, a peaky top.",
     "CUT: cutoff.", "RES: resonance.",
     "A: the audio in.", "B: cutoff modulation."),
    ("ADD", "ADD", "Add", "A + B, plus an offset, times a gain. A mixer that can also shift a control signal.",
     "OFFS: an offset, -1..+1 (64 none).", "GAIN: output gain (0 to 2; 64 = 1).",
     "A: first input.", "B: second input."),
    ("MULT", "MULT", "Multiply", "A x (B + offset), times a gain. The VCA: audio into A, an envelope into B. Also ring modulation (audio into both).",
     "OFFS: added to B (lets some of A through when B is 0).", "GAIN: output gain.",
     "A: the signal.", "B: the controller (unconnected: A times the offset alone)."),
    ("MIX", "MIX", "Mix", "A crossfade from A to B.",
     "MIX: A at 0, B at 127.", "GAIN: output gain.",
     "A: first input.", "B: second input."),
    ("FOLD", "FOLD", "Fold", "A sine wavefolder: drive a smooth wave into it for rich, west-coast overtones.",
     "DRIV: how hard it is folded (1x to 16x).", "OFFS: a bias that makes the folding asymmetric.",
     "A: the audio in.", "B: modulates the drive (an envelope here makes the tone bloom with the note)."),
    ("COMP", "COMP", "Compare", "A comparator: outputs +LEVL when A is above B + THRS, -LEVL otherwise. Makes gates and pulse waves from smooth signals.",
     "LEVL: the output's height.", "THRS: the threshold offset.",
     "A: the signal.", "B: what it is compared with (0 when unconnected)."),
    ("XOR", "XOR", "XOR", "Logic: high when exactly one of A and B is above the threshold. Two pulse waves into XOR: a ring-mod-like square.",
     "LEVL: the output's height.", "THRS: the threshold.",
     "A: first input.", "B: second input."),
    ("FLIP", "FLIP", "Flip", "A flip-flop: each rising edge on A toggles the output; a rising edge on B resets it. Divides a clock or a pitch by 2 (an octave down).",
     "LEVL: the output's height.", "THRS: the edge threshold.",
     "A: the clock.", "B: reset."),
    ("HOLD", "HOLD", "Sample & hold", "Samples A on each trigger and holds it, optionally quantised into steps and glided. Random melodies: NOISE into A.",
     "STEP: quantise into steps (0 = smooth).", "GLID: glide between held values.",
     "A: what is sampled.", "B: the clock (unconnected: each note's TRIG)."),
    ("SKIN", "SKIN", "Skin", "A modal resonator tuned like a drum skin (six circular-membrane modes) at the note. Strike it with SLOPE, IMPULSE or noise: toms, hand drums.",
     "TUNE: the ring time (2 ms to 8 s).", "BRIT: brightness (how long and loud the upper modes are).",
     "A: the exciter (what strikes it).", "B: pitch modulation (a VEL here makes harder hits higher)."),
    ("BAR", "BAR", "Bar", "A modal resonator tuned like a free bar (marimba/glockenspiel modes).",
     "TUNE: the ring time.", "BRIT: brightness.",
     "A: the exciter.", "B: pitch modulation."),
    ("SAT", "SAT", "Saturate", "A soft saturator: warmth and density, with an offset for even harmonics.",
     "DRIV: the drive (1x to 16x).", "OFFS: bias (asymmetry).",
     "A: the audio in.", "B: modulates the drive."),
    ("RUNG", "RUNG", "Rungler", "Rob Hordijk's Rungler (the Benjolin's heart): a shift register clocked by A, fed back on itself or with new bits from B. Outputs a stepped 8-level pattern, chaotic but looping.",
     "LOOP: how likely each step keeps the old bit (high = a locked loop, low = always changing).", "LEN: the register's length (3 to 8 bits).",
     "A: the clock (a CYCLE or a PHASE).", "B: the data bit (unconnected: random)."),
    ("IMPLS", "IMPL", "Impulse", "An impulse train or a single tick: a short rise-fall pulse at the note's rate (or on A's rising edges). Strikes resonators; on its own, a buzzy pulse wave.",
     "RATE: the pulse's width (longer = softer).", "DCAY: the rise/fall balance.",
     "A: clock (fires on rising edges instead of at the note).", "B: shortens or lengthens the pulse."),
    ("CREAS", "CRES", "Crease", "A + B + offset, then the two halves of the wave pushed apart by GAIN: a fold at zero that adds a hard, buzzy edge.",
     "GAIN: how far the halves are pushed apart.", "OFFS: the offset.",
     "A: first input.", "B: second input."),
]
# RIFT v0.16: WEFT's clocks, particles and modular basics (shown when the tree has them)
BLOCKS_17 = [
    ("TICK", "TICK", "Tick", "A clock locked to the Digitone's tempo, like a metro: a one-sample click every DIV, which sounds with CHANCE's probability. Clock a SLOPE, ENV, HOLD, CDIV or RUNG with it for tempo-synced patterns.",
     "RATE: the division of the tempo, 4 bars to a 64th (4 BAR, 2 BAR, 1 BAR, 1/2, 1/4, 1/6, 1/8, 1/12, 1/16, 1/24, 1/32, 1/64).", "CHNC: the chance a tick sounds (127: every one).",
     "A: a gate on it (ticks only while A is up).", "B: swing/humanise: each tick up to half a division late, at random by B's amount."),
    ("ENV", "ENV", "Envelope", "A plain attack/release envelope that follows a gate: rises at ATK while the gate is up, falls at REL after. (SLOPE is attack/decay from a trigger; ENV holds as long as the gate.)",
     "ATK: the attack time.", "REL: the release time.",
     "A: the gate (unconnected: the note's).", "B: scales both times."),
    ("VCA", "VCA", "VCA", "A voltage-controlled amplifier: A times a gain of LEVL plus B, with CURV from linear to a cube (an audio taper). With nothing in A it outputs the gain itself (a control source).",
     "LEVL: the base gain.", "CURV: the response, linear to cubic.",
     "A: the signal.", "B: added to the gain (an envelope here)."),
    ("CDIV", "CDIV", "Clock divider", "Divides or multiplies a clock: a pulse on A's first rise of every RATI rises (/2, /3 ... /64), or RATI evenly spaced pulses between A's rises (x2, x3, x4).",
     "RATI: the ratio (x4, x3, x2, 1, /2, /3, /4, /5, /6, /7, /8, /12, /16, /24, /32, /64).", "WIDT: each pulse's length, a fraction of the divided period.",
     "A: the clock (a TICK, a CYCLE through COMP).", "B: a rise resets the count (back to the first)."),
    ("DUST", "DUST", "Dust", "Random particles in clumps: sparse impulses whose rate is DENS, and each one makes the next more likely for a while (CLMP), so they come in bursts. Strike a SKIN, BAR or BP with it for rain, Geiger clicks, crackle.",
     "DENS: the average rate.", "CLMP: how strongly particles bunch together.",
     "A: modulates the density.", "B: a rise triggers a burst (unconnected: each note)."),
    ("CHAOS", "CHAO", "Chaos", "The logistic map: a value stepped through x = r x (1 - x) at RATE (or at each rise of A). Low R settles into cycles of 2, 4, 8; high R is chaos. A stepped, not-quite-random control source.",
     "R: the map's r, 3.4 to 4.0 (period-doubling into chaos).", "RATE: steps a second (0.1 Hz to audio rate).",
     "A: steps on its rises (instead of RATE).", "B: moves R."),
    ("CRUSH", "CRSH", "Crush", "A bitcrusher and sample-rate reducer: A held for RATE samples at a time, rounded to BITS' levels.",
     "BITS: the resolution (16 bits down to 1).", "RATE: samples each value is held (1 to 64).",
     "A: the audio in.", "B: modulates the hold rate."),
    ("LISSA", "LISA", "Lissajous LFO", "Two sines at a RATI of one RATE (the X and Y of a Lissajous figure); the block outputs X: a complex, slowly repeating LFO shape.",
     "RATE: 0.02 Hz to audio rate.", "RATI: the ratio between them (1:1, 1:2, 2:3, 3:4 ...).",
     "A: modulates the rate.", "B: (unused)."),
]
SOURCES = [("----", "nothing (the input is unused)"),
           ("B1..BC", "another block's output (1-9, then A, B, C for 10-12). An earlier block is heard at once; the block itself or a later one is heard one 32-sample block late (0.67 ms): that is how feedback patches work"),
           ("PTCH", "the note's pitch, as a control signal (0 at middle C, +-1 at four octaves)"),
           ("GATE", "1 while the note is held, 0 after"),
           ("TRIG", "a single pulse at each new note"),
           ("VEL", "the note's velocity, 0..1"),
           ("NOIS", "white noise"),
           ("LFO1", "a sine at page 1's LFO1 rate"),
           ("LFO2", "a sine at page 1's LFO2 rate")]
FACTORY = [
    ("INIT", "A WAVE through a low-pass, with a SLOPE as amp and filter envelope: a plain subtractive voice to start from."),
    ("SYNC LD", "Two PHASEs, the second hard-synced to the first, through WAVE and a filter with an envelope; a CYCLE slowly moves the sync: a sync lead."),
    ("DX BELL", "Two FM pairs (PHASE into WAVE) at bell ratios, each with its own decay: a DX-style bell/electric piano."),
    ("PH DIST", "Phase distortion: an envelope bends a WAVE's phase (CZ-style), with an amp envelope."),
    ("DRONE", "Two detuned oscillators added, through a band-pass swept by a CYCLE, with a slow SLEW on the gate: an evolving drone."),
    ("TANGLE", "A feedback knot: WAVE, FOLD and BP feeding back into each other, slewed by a CYCLE."),
    ("SH BLIP", "A CYCLE clocks a HOLD of noise, which sets a PHASE's pitch: random blips, gated."),
    ("TOMSKIN", "A SLOPE on TRIG strikes a SKIN (velocity bends its pitch), then SAT: a tuned tom."),
    ("PLONK", "A noise burst under a SLOPE strikes a BAR, then SAT: a plucked wooden bar."),
    ("MANGRVE", "An IMPULSE train folded by FOLD with an envelope: a Mangrove-style formant oscillator."),
    ("SPLIT", "MANGRVE's sound with LFO1 moving the impulses' width: a pulse that splits and breathes."),
    ("CREASE", "PHASE through CREASE, moved by a CYCLE, then a low-pass and an envelope: a creased, buzzy tone."),
    ("BENJOLN", "Two CYCLEs cross-modulating, a RUNGLER and a COMP from them, through a low-pass driven by the rungler: a Benjolin."),
]


def table(mod, text, extra=None) -> str:
    out = []
    for page, cs in mod.PAGES.items():
        out.append(f"<h3>{E(page)}</h3><table class=\"ctl\">")
        for c in cs:
            lab = getattr(mod, "LABELS", {}).get(c, c)
            long = mod.LONG_NAMES.get(c, c)
            ch = getattr(mod, "CHOICES", {}).get(c)
            d = text.get(c, "")
            start = ""
            kd = getattr(mod, "KNOB_DEFAULTS", {})
            od = getattr(mod, "OPT_DEFAULTS", {})
            if c in od and ch:
                start = ch[od[c]]
            elif c in kd:
                v = kd[c]
                start = str(v - 64) if c in getattr(mod, "BIPOLAR", ()) else str(v)
            opts = f"<div class=\"dim\">{E(', '.join(ch))}</div>" if ch else ""
            st = f"<div class=\"dim\">starts at {E(start)}</div>" if start != "" else ""
            out.append(f"<tr><th><b>{E(lab)}</b><br><span class=\"dim\">{E(long)}</span></th><td>{E(d)}{opts}{st}</td></tr>")
        out.append("</table>")
    return "\n".join(out)


def nolfo(m) -> str:
    n = [getattr(m, "LABELS", {}).get(c, c) for c in getattr(m, "NO_LFO", ())]
    return f" Not LFO destinations: {', '.join(n)}." if n else " Every control is an LFO destination."


def p(*xs) -> str:
    return "".join(f"<p>{x}</p>" for x in xs)


def ul(*xs) -> str:
    return "<ul>" + "".join(f"<li>{x}</li>" for x in xs) + "</ul>"


def build() -> str:
    from dnfw.fascia import machines as FM
    from dnfw.organ import machines as OM
    from dnfw.silt import machines as SM
    from dnfw.ligature import machines as LM
    from dnfw.digidrum import machines as DM
    TM = importlib.import_module("dnfw.tholet.machines") if HAS_THOLET else None
    PM = importlib.import_module("dnfw.plateau.machines") if HAS_PLATEAU else None
    if PM is not None and not getattr(PM, "LISTED", True):   # v0.21: PLATEAU withdrawn from MACHINE SEL
        PM = None
    CM = importlib.import_module("dnfw.contour.machines") if HAS_CONTOUR else None
    SPM = importlib.import_module("dnfw.spall.machines") if HAS_SPALL else None

    nav = [("start", "Start here"), ("install", "Install &amp; recovery"), ("ui", "Using RIFT's machines"),
           ("fascia", "FASCIA"), ("organ", "ORGAN"), ("silt", "SILT"), ("ligature", "LIGATURE"),
           ("digidrum", "DIGIDRUM")]
    if CM:
        nav.append(("contour", "CONTOUR"))
    if SPM:
        nav.append(("spall", "SPALL"))
    if TM:
        nav.append(("tholet", "THOLET"))
    if PM:
        nav.append(("plateau", "PLATEAU"))
    if HAS_SMEAR:
        nav.append(("smear", "SMEAR"))
    if HAS_GLASS:
        nav.append(("glass", "RUBBER filter"))
    if have("dnfw.mverb.live"):
        nav.append(("mverb", "Master reverb"))
    nav += [("samples", "Sample machines"), ("flex", "FLEX"), ("recorder", "Recorder"),
            ("tuning", "Microtuning"), ("perf", "Performance")]
    nav += [("versions", "Versions")]
    s = []
    newest = next(v for v, _t, _i in VERSIONS if (v != "0.16" or HAS_SMEAR)
                  and (v != "0.17" or HAS_PLATEAU) and (v != "0.18" or HAS_GLASS) and (v != "0.19" or CM))
    s.append(f"<h1>RIFT</h1><p class=\"dim\">The manual · covers v{E(newest)}</p>")
    s.append("<nav>" + "".join(f"<a href=\"#{a}\">{b}</a>" for a, b in nav) + "</nav>")

    s.append("<h2 id=\"start\">Start here</h2>")
    # v0.23 (owner, 2026-11-24): the quick guide, for a first look before the manual
    s.append('<div class="box"><b>New to RIFT?</b> The <a href="rift-quick.html">quick guide</a> lays out every machine\'s controls as the Digitone\'s pages, with FLEX and SMEAR walk-throughs and tips, on one page.</div>')
    s.append(p("<b>RIFT</b> is a second firmware for the Elektron Digitone II (OS 1.11), separate from the DN2 mk2 mod. "
               "It drops the Machinedrum and Monomachine engines and puts new synthesis machines in their place: "
               "<b>FASCIA</b> (physical percussion and tuned bodies), <b>ORGAN</b> (a pipe organ), <b>SILT</b> (material synthesis), "
               "<b>LIGATURE</b> (a patchable block synth), <b>DIGIDRUM</b> (digital drums)"
               + (", <b>CONTOUR</b> (wave terrain synthesis)" if HAS_CONTOUR else "")
               + (", <b>THOLET</b> (a felt/electric piano with a grain cloud)" if TM else "")
               + (", and <b>PLATEAU</b>, an FX machine (a plate reverb on its own track, fed by a BUS of the tracks you choose)" if PM else "") +
               ". Among the sample machines it adds " + ("<b>SMEAR</b> (a granular looper), " if HAS_SMEAR else "")
               + ("and a filter type, <b>RUBBER</b>, on every machine's FLTR page. " if HAS_GLASS else "")
               + "It keeps the Digitakt II sample machines, FLEX, the +Drive library, the recorder, Direct Jump and parameter slides from the mod. "
               "Unofficial: not made or supported by Elektron."))
    s.append(p("Everything below works like the stock Digitone II unless it says otherwise: p-locks, LFOs, slides, kits and sounds, copy/paste, "
               "MIDI. Every RIFT machine control can be p-locked and slid; most are LFO destinations (the few that are not are said)."))

    s.append("<h2 id=\"install\">Install &amp; recovery</h2>")
    s.append(ul("<b>Back up first</b>, every time: the +Drive and your projects with Elektron Transfer.",
                "Build the file in the DN2 Mod Patcher's RIFT section from your own stock files (Digitone II OS 1.11, Digitakt II OS 1.17, Machinedrum UW OS 1.63). It only lets you save a file that is byte for byte the cleared build. Flash it over USB like any OS update.",
                "Keep the stock OS 1.11 file and a DIN MIDI cable for recovery (the patcher's Flash section). The start-up code and the updater are Elektron's own, untouched.",
                "<b>From the DN2 mk2 mod:</b> Perc and Monomachine tracks open as FM Tone. Keep RIFT projects apart from the mod's and stock's: RIFT's machines do not sound on either.",
                "OS 1.11 only. On 1.12 or later, flashing is a downgrade (see the patcher)."))

    s.append("<h2 id=\"ui\">Using RIFT's machines</h2>")
    s.append(ul("<b>MACHINE SEL</b> ([FUNC] + [SYN]): RIFT's machines come after Swarmer, then the sample machines.",
                "<b>Pages:</b> [SYN] steps through a machine's pages (SYN1, SYN2 ...). Each page shows eight controls in two rows of four, laid out like the knobs A-D (top) and E-H (bottom). Each control has a small icon that moves as you turn it; a choice shows its word in a box.",
                "<b>Values</b> show while you turn a knob, while you hold [SYN], or while you hold a trig: the trig's p-locked controls are highlighted, with their locked values.",
                "<b>Choices</b> (word controls) step four detents a choice, never glide, and stay choices under LFOs and slides.",
                "<b>Shortcuts:</b> [FUNC] + turn moves FASCIA's TUNE by octaves and snaps GEOM and SHIFT to 0. [TRK] + CLEAR ([FUNC] + [PLAY]) puts a machine back to its own start values.",
                "<b>Start values:</b> each machine starts at a playable sound when chosen in MACHINE SEL (the tables below say where each control starts; bipolar controls are shown around 0).",
                "<b>Voices and CPU:</b> RIFT's machines share the DSP with the stock ones. When it gets busy, the oldest notes' tails give way first, never the newest note or a held chord. A small <b>CPU</b>, standing in the strip right of the D/H column, shows on a RIFT machine page while the DSP has just had to leave a voice out (v0.23): if you hear a click with CPU showing, the DSP was out of time; with no CPU, it was something else."))

    s.append("<h2 id=\"fascia\">FASCIA</h2>")
    s.append(p("Physical and spectral percussion and tuned bodies. Two exciters (page 1) strike, blow, bow or scatter dust into one or two resonant bodies (page 2): membranes, plates, bars, bells, glass, tubes, strings. Then a spectral stage (page 3) shapes what rings, and page 4 shapes the onset and how the two bodies interact.",
               "<b>How to approach it:</b> pick the body first (BODA), set its pitch (TUNE) and ring (DAMP); then the exciter (TYPA, HARD); then colour (MATL, POS, GEOM). Body B adds a second, related body: start with XMOD EXCITE and raise COUP. Pages 3 and 4 are for character: a little CHAR, CLIK for definition, VARY so repeated hits differ.",
               "<b>Recipes:</b> marimba: BAR, STRIKE, HARD 50, MATL low, DAMP 40. Tubular bell: CHIME, HARD 90, DAMP 20. Bowed glass: GLASS, BOW, DEC high, HARD 40. Snare: MEMB + BUZZ high, CLIK SNAP. Steel drum: PLATE + WATR. Gong: BELL + BODB PLATE, XMOD TRADE, FDBK a little."))
    s.append(p(f"<span class=\"credit\">Concept: De-Pattern.{nolfo(FM)}</span>"))
    s.append(table(FM, FASCIA))

    s.append("<h2 id=\"organ\">ORGAN</h2>")
    s.append(p("A pipe organ from Ravel (the FM-1 firmware): five stops and seven drawbar ranks, with the pipes' chiff and speech, wind, tremulant and celeste (page 2), a percussive attack, mixture and rotor (page 3), and breath you can play like a flute (page 4). Every page 3 and 4 control at 0 is the plain organ.",
               "<b>How to approach it:</b> page 1 is registration: choose a STOP, then pull drawbars. 8' alone is the plainest sound; add 4' and 2' for a principal chorus, 2 2/3' and 1 3/5' for the Cornet, 16' for weight. Page 2 makes it a real instrument: CHIFF and SPEECH for the attack, WIND and AIR for life, CELESTE for shimmer. The church is the Digitone's reverb: send it there.",
               "<b>Recipes:</b> Plenum: PRINCPL, 16' 8' 4' 2' up, MIXT up. Vox celeste: GAMBA, 8' only, CELESTE up. Flute 4': FLUTE, 4' only, CHIFF 60. Played flute: FLUTE, BRTH 60, BLOM 50, EDGE 40, PVEL up. Drawbar organ: PERC 80, KCLK 50, ROTR 70."))
    s.append(p(f"<span class=\"credit\">Concept: De-Pattern (Ravel's organ).{nolfo(OM)}</span>"))
    s.append(table(OM, ORGAN))

    s.append("<h2 id=\"silt\">SILT</h2>")
    s.append(p("Material synthesis: four materials (FIBER, SILT, SKIN, FLUID) played by ten gestures, from a bow to a quake, by one player or an ensemble. You play it in three layers:",
               "<b>1. Choose</b> on page 4 (per trig, p-lockable): what the matter is (MAT), what you do to it (GEST), how many players (MODE), how they are laid out and move (DIST).",
               "<b>2. Shape</b> on pages 1-3: MATTER, CONTACT, STRUCTURE. Each knob is one physical idea that every material reads in its own way (PRESS is always 'how hard').",
               "<b>3. Play:</b> velocity strikes harder and bows faster (and in MASS sets how many players join); the trig's length is how long the gesture is held; LOOP restarts it while held.",
               "<b>STRESS</b> is a hidden macro, how near the matter is to failing, made from PRESS, ROSIN, INST, ROUGH and SCRAP. FIBER squeals and breaks up, SKIN stiffens and jumps, SILT avalanches, FLUID drips faster. It has a soft ceiling so it stays musical.",
               "<b>Pairs to explore:</b> PRESS x ROSIN (stable to squeal); PRESS x SPEED (flautando to crushed); SPREAD x DRIFT x COHE (the cluster); SNAP x VISC on SKIN (pluck to thud); VISC x TENS x SPEED on FLUID (water to honey); GLISS x DIST x SHAPE (the glissando family); MODE MASS against MASS-8.",
               "The start sound is a gently bowed FIBER string, in tune. Page 4 is p-lockable per trig."))
    s.append(p(f"<span class=\"credit\">Concept: De-Pattern.{nolfo(SM)}</span>"))
    s.append(table(SM, SILT))

    # LIGATURE
    s.append("<h2 id=\"ligature\">LIGATURE</h2>")
    s.append(p("A patchable synth voice built from twelve small blocks, after WEFT (the Ravel FM-1's block voice). Each block does one thing (an oscillator, an envelope, a filter, a VCA, logic, a resonator) to its two inputs, A and B, using two settings. You wire blocks into each other and choose which block is the output. The same voice plays every note of the track.",
               "<b>Each project keeps 128 wirings.</b> PATCH (page 1, 1..128) picks which one the track plays, and is p-lockable (a different patch per trig). A new project's wirings start as the 13 factory patches (slots 1-13), then empty INITs."))
    s.append("<h3>Page 1: the PATCH screen</h3>")
    s.append(p("The top of page 1 shows the wiring as a grid of twelve tiles, in WEFT's order: 1-9, then A, B, C (blocks 10-12). Each tile names its block's type. Cables in the gutters show what feeds what; a cable back to an earlier block (feedback) is dotted. The output block is marked. Below the grid are page 1's eight controls in their knobs' places."))
    s.append(ul("<b>[YES]</b> opens <b>EDIT</b> on the selected block:",
                "<b>A BLK</b> picks the block (or use the arrows to move between tiles).",
                "<b>B TYP</b> its type (the 22 blocks below, or empty).",
                "<b>C INA</b> what feeds input A; <b>D AMA</b> how much (-100..+100 %; negative inverts).",
                "<b>E INB</b> what feeds input B; <b>F AMB</b> how much.",
                "<b>G MOV</b> (B MOVES): instead of feeding the block's B input, B moves the block's <i>second setting</i> (once a block, 667 times a second): use it to modulate a setting the block has no input for.",
                "<b>H OUT</b>: which block the voice plays (the output).",
                "<b>[FUNC] + [NO]</b> empties the block. <b>[YES]</b> again shows the <b>BLOCK view</b>: its inputs, its two settings and where it goes. <b>[NO]</b> leaves EDIT.",
                "Every change is heard at once and kept in the project (saved with it)."))
    s.append("<h3>Pages 2-4: the settings</h3>")
    s.append(p("Each block has two settings; pages 2-4 hold them: page 2 blocks 1-4, page 3 blocks 5-8, page 4 blocks 9-12, two knobs a block. Each knob is named for its block and setting (for example <code>1RISE</code>, <code>3CUT</code>). They are <b>offsets</b> from the wiring's own setting: 0 is the patch as wired, so you can p-lock, slide and LFO them around it, and a PATCH change still sounds as designed. A knob whose block is empty does nothing."))
    s.append("<h3>Page 1's controls</h3>")
    s.append(table(type("P1", (), {"PAGES": {"SYN1 PATCH": LM.PAGES["SYN1 PATCH"]}, "LABELS": LM.LABELS, "LONG_NAMES": LM.LONG_NAMES,
                                   "CHOICES": {}, "KNOB_DEFAULTS": LM.KNOB_DEFAULTS, "BIPOLAR": LM.BIPOLAR}),
                   {"PATCH": "Which of the project's 128 wirings the track plays (1..128). P-lockable.",
                    "TUNE": "Tune, +-24 semitones.",
                    "FINE": "Fine tune, +-50 cents.",
                    "LFO1": "The rate of the LFO1 source (0.05 to 25 Hz), a sine any block input can use.",
                    "LFO2": "The rate of the LFO2 source.",
                    "VSNS": "Velocity sense: how much velocity changes the level.",
                    "DRIV": "Drive into a soft clip on the output (up to 8x).",
                    "LEVL": "Level."}))
    s.append("<h3>Sources an input can take</h3><table class=\"ctl\">" +
             "".join(f"<tr><th><b>{E(a)}</b></th><td>{E(b)}</td></tr>" for a, b in SOURCES) + "</table>")
    s.append("<h3>The blocks</h3>")
    s.append(p("Signals are roughly -1..+1 (audio) or 0..1 (envelopes, gates). Any output can feed any input, audio or control: that is the fun of it."
               + (" Since v0.16, TICK, ENV, VCA, CDIV, DUST, CHAOS, CRUSH and LISSA too (the last eight below)." if "TICK" in getattr(LM, "TYPE_SETS", {}) else "")))
    s.append("<table class=\"blk\"><tr><th>Block</th><th>What it does</th><th>Settings (knobs)</th><th>Inputs</th></tr>")
    blocks = list(BLOCKS)
    if "TICK" in getattr(LM, "TYPE_SETS", {}):
        blocks += BLOCKS_17
    for name, short, long_, what, s1, s2, ia, ib in blocks:
        s.append(f"<tr><td><b>{E(short)}</b><br><span class=\"dim\">{E(long_)}</span></td><td>{E(what)}</td>"
                 f"<td>{E(s1)}<br>{E(s2)}</td><td>{E(ia)}<br>{E(ib)}</td></tr>")
    s.append("</table>")
    s.append("<h3>Factory patches</h3><table class=\"ctl\">" +
             "".join(f"<tr><th><b>{i + 1} {E(n)}</b></th><td>{E(d)}</td></tr>" for i, (n, d) in enumerate(FACTORY)) + "</table>")
    s.append("<h3>Patching: worked examples</h3>")
    s.append(ul("<b>A basic voice</b> (INIT): 1 WAVE (free-running), 2 SLOPE (envelope), 3 LP (A from 1, B from 2: the envelope opens the filter), 4 MULT (A from 3, B from 2: the VCA). OUT = 4.",
                "<b>FM:</b> 1 PHASE (RATI 2), 2 WAVE (A from 1: a sine at 2x), 3 PHASE (A from 2, AMA 30 %: 2 modulates its rate), 4 WAVE (A from 3), 5 SLOPE, 6 MULT (A 4, B 5). OUT = 6. Raise AMA on block 3 for more brightness; put a SLOPE into it for a decaying FM index.",
                "<b>A plucked drum</b> (TOMSKIN): 1 SLOPE with A = TRIG (a fast hit), 2 SKIN (A from 1; B from VEL so harder hits are higher), 3 SAT. Change 2 to BAR for a marimba.",
                "<b>Slope pinging a skin, looping:</b> 1 CYCLE (RATE to taste) feeds 2 SLOPE's A (it retriggers at each cycle), 2 into 3 SKIN's A. OUT = 3: a self-playing hand drum. Put LFO1 into the SKIN's B for a pitch wobble.",
                "<b>Random melodies:</b> 1 CYCLE (the clock), 2 HOLD (A = NOIS, B from 1, STEP up to quantise), 3 PHASE (A from 2: the held value moves its pitch), 4 WAVE (A from 3), 5 MULT (A 4, B = GATE). OUT = 5.",
                "<b>Feedback:</b> wire a later block into an earlier block's input (e.g. 4 into 1's A). The return is one block (0.67 ms) late; small amounts thicken, large ones scream. Keep a SAT or a filter in the loop.",
                "<b>Use G MOV</b> when a block's second setting has no input: e.g. on a FOLD, MOV with B = LFO1 sweeps OFFS; on a RUNG, MOV moves LEN."))
    s.append(p(f"<span class=\"credit\">Concept: De-Pattern (WEFT, from Ravel).{nolfo(LM)}</span>"))
    s.append("<h3>Pages 2-4</h3>")
    s.append(table(type("P2", (), {"PAGES": {k: v for k, v in LM.PAGES.items() if k != "SYN1 PATCH"}, "LABELS": LM.LABELS,
                                   "LONG_NAMES": LM.LONG_NAMES, "CHOICES": {}, "KNOB_DEFAULTS": LM.KNOB_DEFAULTS,
                                   "BIPOLAR": LM.BIPOLAR}),
                   {c: "Offset from this block's first setting (named on screen by the block's type)." if c.endswith("A") else
                    "Offset from this block's second setting." for c in LM.CONTROLS if c.startswith("S")}))

    s.append("<h2 id=\"digidrum\">DIGIDRUM</h2>")
    s.append(p("Digital drums after the Syntakt's: six voices picked by TYPE, which a trig can p-lock, so one track can play a whole kit. Page 1's first four controls are shared; its last four (O1..O4) are named on screen by the TYPE. Page 2 is an overdrive, an EQ band, a tremolo, a band-pass window and the level.",
               "<b>Tip:</b> put DIGIDRUM on one track with a TYPE lock on each trig (BD on 1 and 9, SD on 5 and 13, CY on the off-beats); p-lock TUNE and DEC per trig as on a drum machine."))
    s.append(p("<span class=\"credit\">Concept: De-Pattern, after the Syntakt's digital machines (our own synthesis).</span>"))
    s.append(table(DM, DIGIDRUM))
    s.append("<h3>O1..O4 by TYPE</h3><table class=\"ctl\">")
    for t in DM.TYPES:
        cells = "".join(f"<b>{E(o)}</b> {E(DIGIDRUM_OWN.get(o, ''))}<br>" for o in DM.OWN[t])
        s.append(f"<tr><th><b>{E(t)}</b></th><td>{cells}</td></tr>")
    s.append("</table>")

    if CM:
        s.append("<h2 id=\"contour\">CONTOUR</h2>")
        s.append(p("Wave terrain synthesis: a point orbits over a surface, and the height under it is the sound. Page 1 (ORBIT) shapes the path: its size, centre, rotation, the Y:X ratio and a slow drift. Page 2 (LAND) picks the surface and shapes it, then folds, modulates and crushes the result.",
                   "<b>How to approach it:</b> start on SINE with small SIZX and SIZY: a clean tone. Open the sizes and the orbit crosses more of the hills: brighter. Move CNTX and CNTY to find a spot you like, then change SURF and RATIO. DRFT makes held notes evolve; FM and FDBK make it snarl."))
        s.append(p("<span class=\"credit\">Concept: De-Pattern, after wave terrain synthesis (our own code).</span>"))
        s.append(table(CM, CONTOUR))

    if SPM:
        s.append("<h2 id=\"spall\">SPALL</h2>")
        s.append(p("Sound built from tiny events: clicks, dust, tiny tonal grains and digital chips, each one shaped, placed in time by a stochastic clock, and rung through two resonators. One sharp click, or a whole landscape of microscopic activity, from the same machine. Silence matters as much as sound: GAP and CLMP decide the space between. Page 1 (PARTICLES) makes the events and places them; page 2 (SURFACE) gives them their colour and the surface they land on.",
                   "<b>How to approach it:</b> start from the defaults: soft clicks, ringing. Turn DENS for how busy, GAP for how broken, CLMP for clusters. On page 2, move FRQA and FRQB: the same clicks become wood, glass or metal. RING longer and MIX up for pings; TYPE TONE with SPRD up for metallic grains. MEM up makes a phrase repeat exactly; p-lock FRQA on trigs for rhythms made of pitch.",
                   "<b>Like every RIFT synth:</b> a trig starts it; it keeps sounding while the track's AMP lets it, so shape it with the AMP envelope. The name: a spall is a chip thrown off stone under impact."))
        s.append(p("<span class=\"credit\">Concept: De-Pattern, after lowercase and clicks-and-cuts music (our own code).</span>"))
        s.append(table(SPM, SPALL))

    if TM:
        s.append("<h2 id=\"tholet\">THOLET</h2>")
        s.append(p("A piano that leans toward a Rhodes: one of six real grand-piano hammer transients starts each note, two detuned sets of twelve string partials ring under it, a felt layer softens it after Nils Frahm, EP morphs it toward an electric piano, and a grain cloud (page 2) lets the note break up into grains as it fades.",
                   "<b>How to approach it:</b> pick a HAMR and set DEC; FELT for the felt piano, EP for a Rhodes, STRK for warmth. On page 2, raise GRAN and the tail turns into a cloud: GDEN, GSIZ, GSPR shape it, GFM makes it waver. REL is the damper when a note ends (use the trig's length, or HOLD)."))
        s.append(p("<span class=\"credit\">Concept: Error Kit. Hammer samples: Kawai grand (VCSL, CC0).</span>"))
        s.append(table(TM, THOLET))

    if PM:
        s.append("<h2 id=\"plateau\">PLATEAU (an FX machine)</h2>")
        s.append(p("RIFT's first <b>FX machine</b>: a plate reverb after Jon Dattorro's design (the one Valley's Plateau is built on), on a track of its own. "
                   "It doesn't make a sound of its own: it reverberates the tracks on its <b>BUS</b>. Its output is the track's voice, mono, "
                   "so the track's own filter, amp, LFOs, sends, LEVEL, mutes and p-locks all work on the reverb. The tracks you feed it keep their own dry sound: "
                   "turn a source's level down if you want it 100% wet.",
                   "<b>To use it:</b> MACHINE SEL: Plateau on a free track. Give it a long note: a trig with INF length (or hold it with KEYBOARD HOLD); "
                   "the reverb runs while that note sounds, so the track's AMP envelope is the reverb's gate. "
                   "To keep its voice, reserve one for the track in the stock voice allocation menu.",
                   "<b>The BUS page:</b> on the PLATEAU track, <b>[FUNC] + [VOICE]</b> opens it: sixteen cells, one per track. "
                   "[TRIG n] puts track n in or out; its LED is lit while it is in. YES or NO goes back. "
                   "A new PLATEAU track starts with every track in except FLEX tracks and FX tracks (drawn struck through); its own track can never be in. "
                   "The bus is saved with the sound, so it can differ per kit.",
                   "<b>One reverb:</b> the reverb's memory is one, so one PLATEAU track plays at a time: the newest one to start takes it over, and an older one goes quiet. "
                   "When a new PLATEAU starts it clears its memory first (about 15 ms of silence).",
                   "<b>TUNED</b> turns the plate into a resonator at the note's pitch: play it melodically, or hold a note and HOLD the result."))
        s.append("<table>" + "".join(
            f"<tr><th><b>{E(c)}</b><br><span class=\"dim\">{E(PM.LONG_NAMES[c])}</span></th><td>{E(PLATEAU[c])}</td></tr>"
            for c in PM.CONTROLS) + "</table>")

    if HAS_GLASS:
        s.append("<h2 id=\"glass\">RUBBER (a filter type)</h2>")
        s.append(p("A filter type after the Roland SH-101's, on <b>every</b> machine's FLTR page (MACHINE SEL's FLTR list: <b>Rubber</b>, after Equalizer). "
                   "A four-pole low-pass ladder (24 dB a octave) with the 101 chip's soft saturation at its input and in its resonance: "
                   "snappy, squelchy, rubbery mono basslines. Resonance keeps the low end round, and at the top the filter self-oscillates. "
                   "The cutoff glides smoothly however fast the envelope moves it. (v0.24: RUBBER replaced GLASS.)",
                   "<b>Its pages are Multi-Mode's</b>, with these meanings:"))
        s.append(ul("<b>FREQ</b>: the cutoff.",
                    "<b>RES</b>: the resonance, up to self-oscillation at the top (turn KEY.T up and it plays in tune).",
                    "<b>DRIV</b> (in TYPE's place): how hard the signal drives the chip, from clean to thick and rubbery.",
                    "<b>ENV</b>: the envelope's depth on the cutoff, up or down (middle: none), up to six octaves.",
                    "<b>ATK</b> and <b>DEC</b>: RUBBER's own envelope, attack then decay from each trig. SUS and REL are blank on page 1.",
                    "<b>ABND</b> and <b>DBND</b> (page 2, as knobs): the shape of the attack and of the decay: fully left exponential (slow, then fast), the middle straight, fully right logarithmic (fast, then slow). Short DEC with DBND to the left is the 101's snap.",
                    "<b>KEY.T</b>: how far the cutoff follows the note."))
        s.append(p("<b>CPU:</b> RUBBER costs less DSP time a track than GLASS did, and its time counts toward the DSP's budget.",
                   "<b>Note:</b> a sound saved with RUBBER and loaded on stock firmware or the DN2 mk2 mod loads as Multi-Mode. A sound saved with GLASS on v0.18 to v0.23 opens with RUBBER."))

    if HAS_SMEAR:
        s.append("<h2 id=\"smear\">SMEAR</h2>")
        s.append(p("A granular looper after the Qu-Bit Nebulae, in WERP's place among the sample machines (MACHINE SEL: Smear). It plays a sample or a FLEX buffer through readers of one loop: <b>VOC</b>, a keyframe time stretch (v0.26), <b>PLAY</b>, a continuous read whose pitch and speed are apart (two crossfading read heads, v0.24), and <b>GRN</b>, a cloud of grains; BLND moves between them. A note restarts the read at STRT and plays at its pitch (TUNE too), so SMEAR plays chromatically.",
                   "<b>How to approach it:</b> load a sample and play it at BLND 0 (VOC) or 64 (PLAY). Turn BLND up to 127 for grains: DENS, OVLP, SPRY and PRND make it a cloud. Short SIZE loops a small piece; STRT scans. <b>FRZ</b> (page 2) holds the moment as a grain cloud while you play notes over it. LFO SPD, STRT or BLND for motion.",
                   "<b>VOC, the keyframe stretch (v0.26).</b> BLND's VOC end is back, rebuilt on heavylight's keyframe time stretching (Capicola and dt2-keyframer, heavylight-industries; the DAFx26 paper <i>Keyframe Time Stretching via Extrema Sampling</i>), written again for SMEAR with credit and permission. The sample's peaks and troughs are its keyframes. One head moves at SPD (the read point), the other reads at the pitch (TUNE and the note); when they drift apart, the playing head jumps onto the read point's last peak or trough of the same kind with a short crossfade (at most 20 ms, heavylight's). So SPD stretches time without changing pitch, TUNE changes pitch without changing time, and SPD 64 or FRZ holds a moment as a looping grain. It costs a few thousand DSP cycles a voice (the old phase vocoder needed 200,000 and more, and was switched off in v0.18).",
                   "<b>Page 2</b> (v0.22: laid out as ONESHOT's page 2) shows the sample across the screen, with the loop (STRT, SIZE) marked, the read point moving through it and a grain cloud round it (more grains with DENS, wider with SPRY, longer with OVLP). Above the sample, four small pictures for knobs A-D: <b>OVLP</b> two grains that overlap more as it rises; <b>SPRY</b> grains scattered round the read point; <b>PRND</b> grains at random pitches; <b>WIN</b> the window's own shape. Knob E is <b>FRZ</b>, a bar over its label while frozen. Values show as you turn, as on every page."))
        s.append(p("<span class=\"credit\">Concept: De-Pattern, after the Qu-Bit Nebulae v2 (its granular-looper instrument, MIT).</span>"))
        s.append("<h3>SRC page 1</h3><table class=\"ctl\">" + "".join(
            f"<tr><th><b>{E(a)}</b><br><span class=\"dim\">{E(b)}</span></th><td>{E(c)}</td></tr>" for a, b, c in SMEAR[:8]) + "</table>")
        s.append("<h3>SRC page 2</h3><table class=\"ctl\">" + "".join(
            f"<tr><th><b>{E(a)}</b><br><span class=\"dim\">{E(b)}</span></th><td>{E(c)}</td></tr>" for a, b, c in SMEAR[8:]) + "</table>")

    if have("dnfw.mverb.live"):
        s.append("<h2 id=\"mverb\">Master reverb</h2>")
        s.append(p("Since v0.21 the master reverb (the FX block's REVERB page) is a plate: Dattorro's figure-eight tank, the sound of PLATEAU, in stereo. The page and its controls are the stock ones, so sends, routing, LFO destinations and your projects work as before; what they do is:"))
        s.append(ul("<b>PRE</b> (pre-delay): from none to 0.3 s before the plate.",
                    "<b>DEC</b> (decay time): from a short room to a long plate.",
                    "<b>FREQ</b> and <b>GAIN</b> (the feedback shelving): a high shelf inside the tank. FREQ sets its corner (500 Hz to 19 kHz), GAIN how much of the brightness above it survives each pass round the tank: low GAIN, a dark tail that loses its highs fast; full GAIN, a bright one.",
                    "<b>HPF</b>, <b>LPF</b>, <b>MIX VOL</b> and routing are stock's, unchanged, as are the tracks' reverb sends.",
                    "After power-on the plate needs a moment (about 12 ms) to clear its memory; it is silent meanwhile."))
    s.append("<h2 id=\"samples\">Sample machines</h2>")
    s.append(p(("ONESHOT, SMEAR (in WERP's place), STRETCH, REPITCH, GRID, SLICE and FLEX" if HAS_SMEAR else "ONESHOT, WERP, STRETCH, REPITCH, GRID, SLICE and FLEX") + ", from the Digitakt II, play samples from the project's sample list and the +Drive library (16,384 samples, in folders)."))
    s.append(ul("<b>SAMP</b> picks a sample; turning past 127 reaches the eight FLEX buffers <b>B1..B8</b> (\"FLEX BUF n\" when one holds a take): any sample machine can play a FLEX take.",
                "<b>EDIT SLICE POINTS</b> (SLICE, GRID): edits are heard 0.2 s after the knobs rest; the slice that plays is selected; ZOOM shows 128 frames of the sample itself; [FUNC] + START / END snaps to the nearest zero crossing.",
                "<b>CREATE SLICE GRID:</b> [FUNC] + E jumps SLICES 2 / 4 / 8 / 16 / 32 / 64.",
                "<b>GRID's ALLOCATE SLICE:</b> a lock per trig; [NO] keeps RANDOM's locks.",
                "<b>The +Drive library:</b> nested folders, a file browser with marks, SELECT UNUSED, the stock NAME screen for file names."))

    s.append("<h2 id=\"flex\">FLEX</h2>")
    s.append(p("FLEX is a live-buffer machine like the Octatrack's Flex: it records into one of eight buffers (B1..B8) and plays them back with ONESHOT's controls (BUF in SAMP's place). Every sample machine can also play a buffer."))
    s.append(ul("<b>Sources</b> (REC SETUP's SRC): <b>TRK1..16</b> (one track's own sound, before its level and sends: a bounce), <b>IN</b> (the external inputs), <b>MAIN</b> (the whole mix as heard, effects included; a FLEX track sounding is recorded too, the Octatrack way: mute it, or record with TRK, for a clean bounce).",
                *(["<b>BUS</b> (v0.17): the sum of the tracks you choose, each as TRK would record it. Pick them on <b>REC BUS</b>, FLEX REC's third page (RIGHT from REC SETUP): sixteen cells, [TRIG n] puts track n in or out, its LED lit while it is in. It starts with every track but the FLEX tracks (and FX tracks); one track always stays in. MUTE SRC mutes every track on the bus. A loud bus can clip: turn GAIN down."] if HAS_PLATEAU else []),
                "<b>Three ways to record:</b> recorder trigs on their step for R.LEN steps (a one-shot trig records once, then is spent; [YES] [YES] re-arms); <b>Q.REC</b>, trigless: [YES] while playing waits for the next boundary (OFF, 1, 2, 4, 8, 16, 32, 64 steps, or the pattern length); and the recorder's own ARM / R.STRT.",
                "<b>R.LEN</b> counts steps at the pattern's scale; [FUNC] + turn moves it a bar (16 steps) a detent.",
                "<b>MUTE SRC</b>: the source track is silenced in the mix while the FLEX track plays it back (held 0.2 s after the note).",
                "<b>Level</b> (v0.21, the DN2 mk2 mod's v0.71 levels): at GAIN 0 a take plays at its source's level, whether of a track, MAIN or IN. A take of MAIN or IN is recorded as it comes in (never pushed into clipping) and lifted 4 dB on playback to get there. GAIN adds to that.",
                "<b>Saving</b> ([FUNC] + [YES]): the take goes into the next empty sample slot and onto the +Drive, not normalised. (A saved MAIN or IN take plays 4 dB quieter than the buffer did: the save keeps the take as recorded.)",
                "Switching a track to FLEX sets its trig length to INF, so you hear the whole take. A BUF lock on a trig plays that buffer."))

    s.append("<h2 id=\"recorder\">Recorder</h2>")
    s.append(ul("The recorder (the DN2 mk2 mod's) records IN, MAIN or a track into the sample list and the +Drive, with threshold arming, R.STRT on the transport and trimming.",
                "<b>MON</b> (v0.14): knob C on the RECORDER turns monitoring on: with SRC IN, the input is heard through the main out while the recorder is armed or recording, at the level it records. \"MON\" shows in the corner while it is on. It starts OFF and is not saved."))

    s.append("<h2 id=\"tuning\">Microtuning</h2>")
    s.append(ul("One tuning per project, and each of the 16 tracks tuned or not (v0.14).",
                "11 factory tunings: 12-TET, Just Major, Just Minor, Pythagorean, Meantone 1/4, Werckmeister III, Kirnberger III, Vallotti, Arabic Rast, Poole Rod12, Poole12 Min; and USER 1..8.",
                "<b>KB SETUP</b>'s H slot is <b>TUNE</b>: turn it to set the track's tuning; push it to open <b>TUNING</b> (A TUNE, B ROOT, C TRK on/off, D ALL tracks).",
                "[YES] on a USER tuning opens <b>EDIT</b>: A NOTE, B CENT, C .1CT (tenths of a cent), D FROM (a tuning to copy; [FUNC] + [YES] copies it in).",
                "Everything a tuned track plays is retuned: keyboard, trigs, chords, arp and slides, on every RIFT machine. MIDI tracks and MIDI out stay 12-TET; SLICE and GRID are never retuned. Saved with the project."))

    perf = ["<b>Direct Jump:</b> hold [PTN] + [YES] turns it on (DIRECT JUMP ON), [PTN] + [NO] off. A pattern cued with [PTN] + [TRIG] then starts at once, from where the playing pattern was. Kept through power-off.",
            "<b>Parameter slides</b> (Overtone / A4 mk2 style): on the TRIG page's second page, <b>SLD</b> (E) and <b>SLEN</b> (F). A trig with SLD on glides every continuous p-lock from the track's value to the lock over SLEN steps. Works on every RIFT machine control.",
            "<b>SLEN NXT</b> (v0.20, from the DN2 mk2 mod, the Analog Four's rule): SLEN's first choice and what a slide trig with no SLEN lock does: the slide lasts until the track's next trig (a note or a lock trig), round the track's length; with no other trig, the whole length. The fixed lengths (1/8 .. 64 steps) are as before."]
    if True:                                   # v0.22: always (v0.15..v0.21 showed it only with THOLET: lost from the manual since)
        perf.append("<b>KEYBOARD HOLD</b> (v0.15): hold [PTN] and press [KEYBOARD]: KB HOLD ON (again: OFF). It is the stock sustain pedal on all 16 tracks: notes already held stay on when let go, new notes held join them, MIDI notes in and the arpeggiator's keys are held too. HOLD OFF releases them all. The sequencer's notes are not held.")
    s.append("<h2 id=\"perf\">Performance</h2>" + ul(*perf))

    s.append("<h2 id=\"versions\">Versions</h2><p class=\"dim\">Each build contains everything before it; flash only the newest.</p>")
    for vid, title, items in VERSIONS:
        if (vid == "0.16" and not HAS_SMEAR) or (vid == "0.17" and not HAS_PLATEAU) \
                or (vid == "0.18" and not HAS_GLASS) or (vid == "0.19" and not CM):
            continue
        s.append(f"<div class=\"box\" id=\"v{vid}\"><b>v{vid} · {E(title)}</b>" + ul(*items) + "</div>")
    return PAGE_HEAD + "\n".join(s) + "\n</main></body></html>\n"


VERSIONS = [
    ("0.26", "VOC", ["CONTOUR: FDBK's original range is back (v0.20's curve taken out): the feedback exactly as it first was.",
                     "SMEAR's VOC is back: BLND 0 plays a keyframe time stretch after heavylight's Capicola / dt2-keyframer (credit and thanks to heavylight): pitch and time apart, peaks spliced onto peaks, 20 ms fades, a few thousand DSP cycles a voice. PLAY is now at BLND's middle."]),
    ("0.25", "SPALL", ["SPALL, a new synth machine: sound from tiny events (clicks, dust, tonal grains, chips) on a stochastic clock, rung through two resonators; two pages, 16 controls, its own icons and logo.",
                       "MACHINE SEL: the MIDI machine shows a 5-pin DIN socket and MIDI under it.",
                       "Includes v0.24."]),
    ("0.24", "APART", ["RUBBER, a new filter type after the Roland SH-101, in GLASS's place on every machine's FLTR page: a four-pole ladder with the chip's soft saturation, snappy and rubbery, self-oscillating at the top. DRIV in TYPE's place; ABND and DBND as knobs on page 2; SUS and REL blank on page 1 (the curves no longer move the envelope's picture); no LPG.",
                       "SMEAR: pitch and speed apart, as on the Nebulae. TUNE and the note set PLAY's pitch only, through two crossfading read heads; SPD sets the speed only (v0.22 and v0.23 played PLAY as tape). With no transposition at speed 1, PLAY reads exactly as before.",
                       "The knob icons on RIFT's pages: a clean one-pixel ring and pointer (the scaled-up ring looked shaded).",
                       "Includes v0.23."]),
    ("0.23", "STEADY", ["FASCIA's crackle (v0.21, even with one note), its likely cause: the DSP's time guard expected a FASCIA voice to cost one and a half times its last block and, with the master plate's few thousand cycles in the stock's share, left a lone voice out on some blocks. It now expects one and a quarter times (FASCIA, ORGAN, SILT, LIGATURE, DIGIDRUM and CONTOUR); the reserve at the frame's end is unchanged.",
                        "CPU on RIFT's machine pages: shown while the DSP has just left a voice out for time.",
                        "CONTOUR's MACHINE SEL logo: a ridge over a grid, its orbit, a crosshair and the moon.",
                        "Includes v0.22."]),
    ("0.22", "FROST", ["GLASS: the crushed, crackly overload sound fixed. GLASS does the same arithmetic at well under two thirds of the DSP time (same sound, bit for bit), and its time now counts toward the DSP's budget, so a busy DSP drops the oldest tails instead of running over.",
                       "SMEAR: TUNE and the note now move PLAY (as tape: higher is faster). Before, at BLND 0 they did nothing.",
                       "SMEAR: FRZ (Freeze), page 2's knob E: holds the read point and turns PLAY's share into grains, so the frozen moment keeps sounding.",
                       "SMEAR: page 2 laid out as ONESHOT's: a big sample view, and small pictures of what OVLP, SPRY, PRND and WIN do.",
                       "CONTOUR has its own MACHINE SEL logo: a terrain's contour lines.",
                       "The manual brought up to date: KEYBOARD HOLD back in Performance, FLEX levels as they are since v0.21, SMEAR's VOC status said plainly, a removed machine no longer listed.",
                       "Includes v0.21."]),
    ("0.21", "PLATE", ["The master reverb is now a plate (PLATEAU's tank, in stereo): the stock REVERB page and its controls, a new sound behind them.",
                      "A new start-up logo: the smoke gathers into RIFT in block letters, which then drip and decompose.",
                      "PLATEAU withdrawn for rework (it glitched with input gain and did not flow with the trigs): out of MACHINE SEL, and a saved PLATEAU track opens as FM Tone.",
                      "FLEX record levels from the DN2 mk2 mod's v0.71: a take of a track, of MAIN or of IN plays at its source's level at GAIN 0.",
                      "Includes v0.20."]),
    ("0.20", "NXT", ["Slides: SLEN NXT (from the DN2 mk2 mod v0.66): a slide lasts until the track's next trig. It is the default for a slide trig with no SLEN lock (before: 1 step).",
                     "CONTOUR: FDBK rescaled (the old range past about 36 was unusable): the whole knob now spans the usable range, with the subtle low end spread over its first third.",
                     "CONTOUR: FDBK and FM stay in key on high notes. Up to B3 every note sounds exactly as before; above it, a voice with feedback keeps B3's behaviour transposed (the feedback follows the pitch, and the orbit takes 2 or 4 steps a sample). A high CONTOUR note with FDBK up costs the DSP more, up to about four times.",
                     "Includes v0.19."]),
    ("0.19", "CONTOUR", ["CONTOUR, a new wave terrain synth machine: an orbit over one of eight surfaces, two pages, 16 controls.",
                         "RIFT's machine pages drawn at the stock size: the icons are larger and the page fills the screen.",
                         "SMEAR: page 2 shows the sample, the loop, the read point and a grain cloud that grows out of it with DENS, SPRY and OVLP.",
                         "Includes v0.18."]),
    ("0.18", "GLASS", ["The silent unit fixed: SMEAR's VOC off (it overran the DSP's frame), the time guard expects a voice's peak cost, and an output guard on every RIFT machine (nothing non-finite or runaway reaches the effects or the master). PLATEAU no longer dropped beside other tracks.",
                       "MACHINE SEL: PLATEAU in its own section (FX), SMEAR first of the sample machines, their own logos.",
                       "GLASS, a new filter type after the Serge VCFQ, on every machine's FLTR page: rings like glass at high RES, never clips, keeps the low end; its own envelope with ATTACK and DECAY BEND, and an LPG.",
                       "Includes v0.17."]),
    ("0.17", "PLATEAU", ["PLATEAU, RIFT's first FX machine: a plate reverb on its own track, fed by a BUS of the tracks you choose ([FUNC] + [VOICE] on its track).",
                         "FLEX: SRC BUS records the sum of chosen tracks; REC BUS, a third page of FLEX REC (RIGHT from REC SETUP), picks them with the [TRIG] keys. MUTE SRC mutes every track on the bus.",
                         "DIGIDRUM's MACHINE SEL logo is the owner's drum hit.",
                         "Includes v0.16."]),
    ("0.16", "SMEAR", ["SMEAR, a granular, phase-vocoded, stretchy looper after the Qu-Bit Nebulae, in WERP's place.",
                       "LIGATURE: eight new blocks from WEFT: TICK (a clock on the tempo, with CHANCE), ENV, VCA, CDIV (clock divider), DUST, CHAOS, CRUSH, LISSA (a Lissajous LFO).",
                       "ORGAN's and SMEAR's tables come from the ColdFire at power-on (the DSP's upload had no room): both are silent for the first moment after power-on.",
                       "Includes v0.15."]),
    ("0.15", "HOLD", ["KEYBOARD HOLD from the DN2 mk2 mod: [PTN] + [KEYBOARD].",
                        "Includes v0.14."]),
    ("0.14", "MONTUNE", ["FLEX takes of MAIN and IN play 12 dB louder (recorded as they come in, never clipped; thanks Error Kit). Takes of a single track are unchanged.",
                         "MON on the RECORDER (knob C), from the DN2 mk2 mod.",
                         "MICROTUNING, from the DN2 mk2 mod: 11 factory tunings, USER 1..8, per track, saved with the project.",
                         "Known: a saved MAIN/IN FLEX buffer plays 12 dB quieter than the buffer did; ERASE MOD DATA doesn't clear the tunings yet."]),
    ("0.13", "PARITY", ["From the DN2 mk2 mod: EDIT SLICE POINTS plays edits without YES, selects the slice that plays, zooms to 128 frames, and FUNC + E / FUNC + H snap START / END to zero crossings.",
                        "CREATE SLICE GRID: FUNC + E jumps SLICES 2 / 4 / 8 / 16 / 32 / 64.",
                        "GRID's ALLOCATE SLICE: NO keeps RANDOM's locks.",
                        "FLEX: a take of a track plays about as loud as the track, GAIN 0 (24 dB more than before); saving a FLEX buffer no longer normalises it."]),
    ("0.12", "PATCHING", ["LIGATURE: patch it yourself. Page 1 shows the wiring as tiles and cables; YES opens EDIT.",
                          "Each project keeps 128 wirings; PATCH (1..128) picks one, p-lockable. They start as the old patches, so earlier LIGATURE tracks sound the same.",
                          "Pages 2-4: each knob named for its block's setting (1RISE, 3CUT ...)."]),
    ("0.11", "VOICEKEEP", ["Held notes keep the CPU: on a busy track a melody's or a re-struck note's tail is dropped before a held chord's notes (dreamsaremaps)."]),
    ("0.10", "DIGIDRUM", ["DIGIDRUM: six Syntakt-style digital drum voices, the TYPE p-lockable per trig.",
                          "A v0.8 RESONATOR track never re-saved in v0.9 opens as DIGIDRUM, with odd settings."]),
    ("0.9", "LINE", ["LINE, the new screen for every RIFT machine.", "Values show the Syntakt way.", "LIGATURE is in MACHINE SEL.",
                     "RESONATOR is removed; a saved RESONATOR track opens as FM Tone."]),
    ("0.8", "RESONATOR", ["RESONATOR (removed again in v0.9)."]),
    ("0.7", "FLEXPOOL", ["FLEX buffers B1-B8 in every sample machine's SAMP; MUTE SRC only while the FLEX track plays; the stock NAME screen for file names; turned knobs show their value."]),
    ("0.6", "SILT", ["SILT, RIFT's third machine."]),
    ("0.5", "BREATH", ["ORGAN pages 3 (ATTACK) and 4 (BREATH)."]),
    ("0.4", "ORGAN", ["ORGAN, RIFT's second machine."]),
    ("0.3", "FLEX", ["FLEX from the DN2 mk2 mod."]),
    ("0.1", "FASCIA", ["FASCIA; the Machinedrum and Monomachine engines removed (their tracks open as FM Tone)."]),
]

PAGE_HEAD = """<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RIFT manual</title><link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;600;700&display=swap" rel="stylesheet"><style>
:root{--bg:#0a0b0c;--panel:#0f1012;--line:#33363b;--text:#ecebe7;--dim:#9a9da3;--acc:#5fe3b0;color-scheme:dark}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.55 'Space Grotesk',ui-sans-serif,system-ui,-apple-system,'Segoe UI',sans-serif}
main{max-width:900px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:28px;margin:0 0 4px;letter-spacing:.04em}h2{font-size:20px;margin:40px 0 8px;padding-top:12px;border-top:1px solid var(--line);letter-spacing:.03em}
h3{font-size:15px;margin:22px 0 6px;color:var(--acc);letter-spacing:.06em}
.dim{color:var(--dim)}a{color:var(--acc)}code,.mono{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-size:13px}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:14px 0 0;font-size:14px;position:sticky;top:0;background:var(--bg);padding:8px 0;z-index:2;border-bottom:1px solid var(--line)}
table{border-collapse:collapse;width:100%;margin:6px 0 4px;font-size:14px}
td,th{border:1px solid var(--line);padding:6px 9px;text-align:left;vertical-align:top}
.ctl th{width:19%;font-weight:400}.ctl b,.blk b{font-family:'JetBrains Mono',ui-monospace,Consolas,monospace;font-size:13px;letter-spacing:.04em}
.ctl td .dim{font-size:13px;margin-top:3px}
.blk th{color:var(--dim);font-weight:600}.blk td:first-child{width:12%}.blk td:nth-child(3),.blk td:nth-child(4){width:24%;font-size:13px}
.credit{font-size:13px;color:var(--dim)}.box{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:12px 0}
ul{padding-left:20px}li{margin:4px 0}
:target{scroll-margin-top:56px}
.pdfbtn{position:fixed;top:10px;right:14px;z-index:20;font:600 13px/1 'Space Grotesk',ui-sans-serif,system-ui,sans-serif;letter-spacing:.04em;color:#fff;background:#8a2a3c;border:1px solid #b04a5c;border-radius:8px;padding:9px 13px;text-decoration:none}.pdfbtn:hover{background:#a0344a}@media print{.pdfbtn{display:none}}
</style></head><body><a class="pdfbtn" href="rift-manual.pdf" download title="The manual as one PDF">Download PDF</a><main>
"""


def main(argv=None) -> int:
    a = argparse.ArgumentParser()
    a.add_argument("--out", default=str(ROOT / "site" / "rift-manual.html"))
    o = a.parse_args(argv)
    pathlib.Path(o.out).write_text(build(), encoding="utf-8")
    print(f"wrote {o.out}{' (with THOLET)' if HAS_THOLET else ''}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
