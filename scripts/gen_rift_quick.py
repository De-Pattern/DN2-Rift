#!/usr/bin/env python3
"""RIFT's quick guide (site/rift-quick.html), to the owner's own design (2026-11-24,
"RIFT Visual Quick Start v0.22 EXPLAINED": a dark quick-reference, one page per machine, each
synth page as the Digitone's knob grid A-D over E-H with what every knob does, a FIRST SOUND
strip). The owner's text is kept; corrections against src/dnfw/*/machines.py PAGES and the manual.
Served next to the MANUAL button on both patchers and linked from the manual's top.

    python3 scripts/gen_rift_quick.py [--out site/rift-quick.html]
"""
from __future__ import annotations

import argparse
import base64
import html
import io
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
LOGOS = ROOT / "src" / "dnfw" / "waverider" / "logos"
COVERS = "0.29"            # the release the guide describes (not VERSION: the tree may be ahead)
LOGO_REF = "v26"           # logos as this release draws them (SPALL's, MIDI's; CONTOUR's crosshair)
TEAL = (111, 199, 180)

def E(s: str) -> str:
    """escaped, the owner's "->" drawn as an arrow (it no longer breaks across lines)"""
    return html.escape(s).replace("-&gt;", "\u2192").replace("&lt;\u2192", "\u2194").replace("&lt;-", "\u2190")


def logo_png(name: str) -> bytes | None:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "show", f"{LOGO_REF}:src/dnfw/waverider/logos/{name}.png"],
                              capture_output=True, check=True).stdout
    except Exception:
        p = LOGOS / f"{name}.png"
        return p.read_bytes() if p.exists() else None


def logo(name: str | None) -> str:
    """The MACHINE SEL logo, its lit pixels teal on a clear ground, drawn 2x pixelated"""
    if not name:
        return ""
    raw = logo_png(name)
    if not raw:
        return ""
    from PIL import Image
    im = Image.open(io.BytesIO(raw)).convert("L")
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    px, po = im.load(), out.load()
    for y in range(im.size[1]):
        for x in range(im.size[0]):
            if px[x, y] > 127:
                po[x, y] = TEAL + (255,)
    b = io.BytesIO()
    out.save(b, "PNG")
    return (f'<img class="logo" alt="" width="{im.size[0] * 2}" height="{im.size[1] * 2}" '
            f'src="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}">')


# ---- the pages ---------------------------------------------------------------------------------
# panel kinds: ("knobs", title, caption, [(name, text) x8])   -- A-H chips
#              ("concept", title, caption, [(name, text) ...]) -- no chips: ideas, not knob places
#              ("kv", title, [(key, text) ...])
#              ("steps", [(title, text) ...])                 -- numbered cards
#              ("cards", [(name, tag, lead, text) ...])       -- the sample machines
#              ("box", title, [text, ...])

def K(*pairs):
    return list(pairs)


PAGES = [
    dict(id="fascia", title="FASCIA", tag="SYNTH MACHINE", logo="fascia",
         sub="Two exciters drive resonant objects; every control tells you which physical behaviour changes.",
         panels=[("knobs", "SYN1 / EXCITERS", "WHAT HITS THE BODY", K(
             ("TYPA", "Select the main exciter: STRIKE / BLOW / BOW / DUST / PULSE / TZFM."),
             ("TYPB", "Choose a second exciter for hybrid attacks."),
             ("HARD", "Soft mallet -> hard tip; bow pressure; breath brightness."),
             ("DUST", "Extra grit, rosin noise or micro-impacts."),
             ("TZFM", "Metallic FM edge; more = harsher."),
             ("BEND", "Pitch glides with the body's level, like a struck skin."),
             ("MIX", "Balance exciter A against exciter B."),
             ("DEC", "Exciter duration: tap -> sustained rub."))),
             ("knobs", "SYN2 / RESONATORS", "WHAT RINGS", K(
                 ("BODA", "Choose resonator: membrane, plate, bar, bell, glass, string..."),
                 ("BODB", "Optional second body; OFF disables it."),
                 ("TUNE", "Body pitch relative to the note. [FUNC]+turn: octaves."),
                 ("GEOM", "Harmonic/woody -> inharmonic/metal. [FUNC]+turn: centre."),
                 ("MATL", "High harmonics die fast -> ring longer."),
                 ("POS", "Strike location; changes overtone mix."),
                 ("COUP", "How strongly A excites body B."),
                 ("DAMP", "LOW = long ring; HIGH = short thud."))),
             ("knobs", "SYN3 / SPECTRAL", "HOW IT SOUNDS", K(
                 ("MORPH", "Spectral colour changes over the tail."),
                 ("FORM", "Vowel-like resonances: a/e/i/o/u."),
                 ("SHIFT", "Frequency shift: beats -> alien clang. [FUNC]+turn: 0."),
                 ("RING", "Ring-modulate the resonators together."),
                 ("SIDE", "Sideband ratio for the TZFM exciter."),
                 ("FOLD", "Wavefold for bright buzzy harmonics."),
                 ("LPG", "Darker and quieter as the note dies."),
                 ("CHAR", "Output saturation: warmth -> grit."))),
             ("knobs", "SYN4 / ONSET", "HOW IT STARTS", K(
                 ("ATK", "Smeared strike / slower bow or breath."),
                 ("CLIK", "Amount of extra attack click/thump."),
                 ("CTYP", "Click type: SNAP / TICK / NOISE / THUMP."),
                 ("XMOD", "Body A acts on B: EXCITE / BEND / CHOKE / TRADE."),
                 ("FDBK", "B feeds A; sustain -> self-oscillation."),
                 ("BUZZ", "Snare-wire / sitar-style contact rattle."),
                 ("WATR", "Gurgling upper spectral water tones."),
                 ("VARY", "Per-hit change; less machine-gun repeat.")))],
         first=("MARIMBA", "BODA BAR -> TYPA STRIKE -> HARD 50 -> DAMP 40"), foot="KNOB BY KNOB"),
    dict(id="organ", title="ORGAN", tag="SYNTH MACHINE", logo="organ",
         sub="Each drawbar changes a pipe rank; other pages add breath, attack, chorus and motion.",
         panels=[("knobs", "SYN1 / RANKS", "DRAWBAR LEVELS", K(
             ("STOP", "Pipe family: flute, nachthorn, principal, gamba, trumpet."),
             ("16FT", "Sub octave; adds bass weight."), ("8FT", "Fundamental note; start here."),
             ("4FT", "1 octave up; adds brightness."), ("NAZ", "Octave + fifth; hollow colour."),
             ("2FT", "2 octaves up; bright upper rank."), ("TIER", "2 octaves + third; reedy colour."),
             ("1FT", "3 octaves up; highest sparkle."))),
             ("knobs", "SYN2 / PIPES", "MAKE IT BREATHE", K(
                 ("CHIFF", "Breathy puff at the note onset."), ("SPCH", "Pipe speech: instant -> slow bloom."),
                 ("SPRD", "Slight rank detune; natural chorus."), ("AIR", "Airflow noise under the organ tone."),
                 ("WIND", "Bellows wobble of pitch / volume."), ("TREM", "Pulsing wind / tremulant depth."),
                 ("RATE", "Speed of the tremulant pulse."), ("CELST", "Sharp detuned rank; shimmering beats."))),
             ("knobs", "SYN3 / ATTACK", "ADD CHARACTER", K(
                 ("PERC", "Hammond-like ping on note attack."), ("PDEC", "How long the percussion ping decays."),
                 ("MTUN", "Tune the added mixture ranks down."), ("KCLK", "Mechanical keyboard click amount."),
                 ("MCHR", "Character / timbre of mixture pipes."), ("MIXT", "Extra high organ pipes; bright crown."),
                 ("ROTR", "Rotating-speaker swirl depth."), ("RSPD", "Speed of the spinning rotor."))),
             ("knobs", "SYN4 / BREATH", "FLUTE-LIKE PLAYING", K(
                 ("BRTH", "Amount of breath / jet turbulence."), ("TURB", "Speed of turbulent breath flutter."),
                 ("BREK", "Voice break / subharmonic growl."), ("BDEP", "How strong the voice break becomes."),
                 ("PRES", "Breath pressure; sharper, break-prone."), ("BLOM", "Breath grows slowly into full note."),
                 ("EDGE", "Audible air-edge noise during bloom."), ("PVEL", "Velocity changes blowing pressure.")))],
         first=("PIPE CHORUS", "STOP PRINCPL -> raise 8FT -> add 4FT + 2FT -> increase MIXT"), foot="KNOB BY KNOB"),
    dict(id="silt", title="SILT", tag="SYNTH MACHINE", logo="silt",
         sub="Select material and playing gesture first, then shape its mass, friction and ensemble.",
         panels=[("knobs", "SYN1 / MATTER", "WHAT IT IS MADE OF", K(
             ("PART", "Stiffness or grain size; gut -> wire."), ("TENS", "Tension / elasticity of material."),
             ("MASS", "Physical size / weight; light -> heavy."), ("COHE", "Players or grains separate -> bind."),
             ("VISC", "Damping / thickness; water -> honey."), ("GRAIN", "Grain or friction-stroke duration."),
             ("DENS", "Crackle / particle or player density."), ("BODY", "Amount of resonant body in the tone."))),
             ("knobs", "SYN2 / CONTACT", "HOW YOU TOUCH IT", K(
                 ("PRESS", "How hard the material is pressed."), ("SPEED", "Bow / scrape / melt / gesture movement rate."),
                 ("POS", "Where it is struck: edge -> middle."), ("ROSIN", "Grip and stick-slip; more squeal."),
                 ("SCRAP", "Irregular rubbing / scraping."), ("SNAP", "Sharpness of impact / transient."),
                 ("AIR", "Breath, dust or liquid-air noise."), ("INST", "Instability; closer to breaking."))),
             ("knobs", "SYN3 / STRUCTURE", "HOW IT MOVES", K(
                 ("SPRD", "How wide / detuned the cluster is."), ("VOICE", "How many layers / ensemble players."),
                 ("DRIFT", "Slow detuning of each player."), ("VIBR", "Vibrato strength / movement."),
                 ("GLISS", "Pitch scoop or travelling glissando."), ("FORM", "Energy-driven band-pass colour."),
                 ("ROUGH", "Friction and scattered impact timing."), ("MORPH", "Tonal pitch -> broken particles."))),
             ("knobs", "SYN4 / CONFIG", "CHOOSE PERFORMANCE (P-LOCK PER TRIG)", K(
                 ("MAT", "FIBER / SILT / SKIN / FLUID."), ("GEST", "BOW / SCRAPE / STACC / TREMO / SPICC / LEGNO / GLISS / FRACT / SWELL / QUAKE."),
                 ("MODE", "SOLO / MASS / MASS-8 / SWARM."), ("DIST", "Cluster layout and gliss motion."),
                 ("LOOP", "Repeat gesture while key is held."), ("SHAPE", "Soft / linear / exp / chaotic curve."),
                 ("TUNE", "FREE / SCALE / MICRO / HARM."), ("QUAL", "ECO / NORMAL / DEEP (DSP cost).")))],
         first=("BOWED ENSEMBLE", "SYN4 MAT FIBER + GEST BOW + MODE MASS -> SYN2 PRESS + ROSIN -> SYN3 SPRD"), foot="KNOB BY KNOB"),
    dict(id="ligature", title="LIGATURE", tag="SYNTH MACHINE", logo="ligature",
         sub="A modular patch: choose a wiring, edit its blocks, then automate per-block offsets.",
         panels=[("knobs", "SYN1 / PATCH CONTROLS", "1-13 FACTORY PATCHES", K(
             ("PATCH", "Select one of 128 stored wirings (p-lockable)."), ("TUNE", "Transpose entire voice, +/-24 semitones."),
             ("FINE", "Fine tuning, +/-50 cents."), ("LFO1", "Speed of modulation source LFO 1."),
             ("LFO2", "Speed of modulation source LFO 2."), ("VSNS", "How much velocity changes level."),
             ("DRIVE", "Output soft clipping / distortion."), ("LEVEL", "Total voice volume."))),
             ("knobs", "[YES] EDIT / BLOCK WIRING", "EDITOR ENCODERS A-H", K(
                 ("BLK", "Choose one of the 12 patch blocks."), ("TYP", "Choose oscillator / filter / logic / etc."),
                 ("INA", "Source feeding the first input."), ("AMA", "Amount of input A; negative inverts."),
                 ("INB", "Source feeding the second input."), ("AMB", "Amount of input B."),
                 ("MOV", "Input B moves the block's second setting instead."), ("OUT", "Select the block you hear."))),
             ("knobs", "SYN2 / BLOCKS 1-4", "0 = PATCH AS WIRED", K(
                 ("1A", "Block 1: offset for its first setting."), ("1B", "Block 1: offset for its second setting."),
                 ("2A", "Block 2: first setting."), ("2B", "Block 2: second setting."),
                 ("3A", "Block 3: first setting."), ("3B", "Block 3: second setting."),
                 ("4A", "Block 4: first setting."), ("4B", "Block 4: second setting."))),
             ("knobs", "SYN3 / BLOCKS 5-8", "NAMES DEPEND ON BLOCK", K(
                 ("5A", "Block 5: first setting."), ("5B", "Block 5: second setting."),
                 ("6A", "Block 6: first setting."), ("6B", "Block 6: second setting."),
                 ("7A", "Block 7: first setting."), ("7B", "Block 7: second setting."),
                 ("8A", "Block 8: first setting."), ("8B", "Block 8: second setting."))),
             ("knobs", "SYN4 / BLOCKS 9-12", "e.g. 9RISE, 11CUT ON SCREEN", K(
                 ("9A", "Block 9: first setting."), ("9B", "Block 9: second setting."),
                 ("10A", "Block 10: first setting."), ("10B", "Block 10: second setting."),
                 ("11A", "Block 11: first setting."), ("11B", "Block 11: second setting."),
                 ("12A", "Block 12: first setting."), ("12B", "Block 12: second setting."))),
             ("box", "EDIT KEYS", ["[YES] opens EDIT on the selected tile; [YES] again shows the BLOCK view.",
                                   "[FUNC]+[NO] empties the block. [NO] leaves EDIT. Every change is heard at once and saved with the project.",
                                   "On SYN2-4 each knob is named on screen by its block's setting (1RISE, 3CUT...): offsets, so p-locks and LFOs move around the patch as wired."])],
         first=("PATCH A VOICE", "SYN1 PATCH 1 -> [YES] edit -> e.g. PHAS -> WAVE -> LP -> MULT (SLOP into B) as OUT"), foot="KNOB BY KNOB"),
    dict(id="ligblocks", title="LIGATURE / BLOCKS", tag="SYNTH MACHINE", logo="ligature",
         sub="What each block type does, and what an input can listen to.",
         panels=[("concept", "SOUND + SHAPE", "OSCILLATORS / FILTERS / RESONATORS", K(
             ("PHAS", "Ramp oscillator at the note x a ratio; FM on A, sync on B."), ("WAVE", "Waveshaper osc: sine -> tri -> saw -> square."),
             ("LP / BP / HP", "Resonant 12 dB filter outputs; B moves the cutoff."), ("SKIN", "Drum-skin resonator: strike it for toms."),
             ("BAR", "Free-bar resonator: marimba / glock."), ("IMPL", "Impulse train or tick: strikes resonators."),
             ("FOLD", "Sine wavefolder: west-coast overtones."), ("SAT", "Soft saturator with even-harmonic bias."),
             ("CRES", "A fold at zero: a hard, buzzy edge."), ("CRSH", "Bitcrusher and sample-rate reducer."))),
             ("concept", "CONTROL + LOGIC", "ENVELOPES / LFOS / CLOCKS", K(
                 ("SLOP", "Attack/decay envelope from each note."), ("ENV", "Attack/release that holds with the gate."),
                 ("CYCL", "LFO / slow oscillator, triangle to ramp."), ("LISA", "Lissajous LFO: complex slow shapes."),
                 ("SLEW", "Lag / portamento, up and down times."), ("HOLD", "Sample & hold, optional steps and glide."),
                 ("TICK", "Tempo-locked clock with chance."), ("CDIV", "Clock divider / multiplier."),
                 ("RUNG", "Rungler: chaotic looping 8-step pattern."), ("CHAO", "Logistic map: stepped chaos."),
                 ("DUST", "Random clumped impulses: rain, crackle."))),
             ("concept", "MIX + MATH", "VCAs / COMPARATORS", K(
                 ("ADD", "A + B + offset, times gain."), ("MULT", "A x (B + offset): the VCA, ring mod."),
                 ("VCA", "Gain with a linear -> audio-taper curve."), ("MIX", "Crossfade A -> B."),
                 ("COMP", "Comparator: gates and pulses."), ("XOR", "Logic: high when one of A/B is high."),
                 ("FLIP", "Flip-flop: divides a clock or pitch by 2."))),
             ("kv", "INPUT SOURCES", [("B1..BC", "Another block (1-9, A, B, C). A later block or itself: one block late = feedback."),
                                      ("PTCH", "The note's pitch as a control"), ("GATE", "1 while the note is held"),
                                      ("TRIG", "A pulse at each new note"), ("VEL", "Velocity 0..1"), ("NOIS", "White noise"),
                                      ("LFO1 / LFO2", "Sines at SYN1's LFO rates")])],
         first=("RINGING DRUM", "IMPL (TRIG into A) -> SKIN as OUT -> raise its TUNE (ring time)"), foot="BLOCK BY BLOCK"),
    dict(id="digidrum", title="DIGIDRUM", tag="SYNTH MACHINE", logo="digidrum",
         sub="TYPE selects six digital drum models. Their last four knobs take on new meanings per type.",
         panels=[("knobs", "SYN1 / DRUM", "O1-O4 CHANGE WITH TYPE", K(
             ("TYPE", "Select kick, snare, clap, cymbal, perc (p-lockable)."), ("TUNE", "Pitch of selected drum type."),
             ("PNCH", "Extra front-end snap and body."), ("DEC", "Volume tail: tight -> long."),
             ("O1", "Type-specific: e.g. pitch sweep."), ("O2", "Type-specific: e.g. FM or balance."),
             ("O3", "Type-specific: e.g. body / overtone."), ("O4", "Type-specific: e.g. mod decay."))),
             ("knobs", "SYN2 / TONE", "SHAPE EACH HIT", K(
                 ("OVER", "Overdrive: warm -> crushed."), ("EQF", "Choose EQ band frequency."),
                 ("EQG", "Cut or boost selected EQ band (64 flat)."), ("AMD", "Amplitude modulation / tremolo depth."),
                 ("AMF", "Tremolo speed -> audio-rate sidebands."), ("FLTF", "Bottom frequency of filter window."),
                 ("FLTW", "Width of band-pass filter window."), ("LEV", "Overall drum output level."))),
             ("kv", "O1-O4 / KICK + SNARES", [("BD MODERN", "SWEP pitch drop · SMOD gritty square mod · TMOD softer triangle mod · MENV mod envelope length"),
                                             ("SD BASIC", "SWEP attack pitch drop · INHM drum -> metallic · MDFB tone -> rattle · MENV"),
                                             ("SD VINTAGE", "SWEP · INHM · FCMP denser, brighter body · MENV")]),
             ("kv", "O1-O4 / CLAP + CYMBAL + PERC", [("CP VINTAGE", "SPCR time between claps · BAL hands vs body · BODY thump -> ringing FM body · BENV body decay"),
                                                    ("CY ALLOY", "SHIM metallic osc ratio · RADIO metallic colour · MOD FM between oscillators · MENV"),
                                                    ("PC CARBON", "SWEP pitch drop · INHM drum -> metal · MOD FM amount · MENV")])],
         first=("ONE-TRACK KIT", "Lock TYPE BD on trigs 1 + 9; TYPE SD on 5 + 13; tune each hit independently"), foot="KNOB BY KNOB"),
    dict(id="contour", title="CONTOUR", tag="SYNTH MACHINE", logo="contour",
         sub="A moving point samples a terrain; the height along its orbit becomes an audible waveform.",
         panels=[("knobs", "SYN1 / ORBIT", "SHAPE THE PATH", K(
             ("TUNE", "Transpose pitch of the repeated orbit."), ("RATIO", "Y vs X orbit speed; circles -> knots / loops."),
             ("SIZX", "Horizontal travel: tiny -> wide."), ("SIZY", "Vertical travel: tiny -> wide."),
             ("CNTX", "Move orbit left / right on terrain."), ("CNTY", "Move orbit up / down on terrain."),
             ("ROT", "Rotate path through the landscape."), ("DRFT", "Slowly evolve orbit while note holds."))),
             ("knobs", "SYN2 / LAND", "SHAPE THE SURFACE", K(
                 ("SURF", "Terrain: SINE / FOLD / CHEB / FM / RING / EDGE / CHAOS / BITS."),
                 ("MORPH", "Reshape the terrain for character."), ("WARP", "Bend or distort the orbit's coordinates."),
                 ("FOLD", "Fold the result for harmonics."), ("FM", "Output speeds up / slows the orbit: growl."),
                 ("FDBK", "Output pushes the orbit: thickens -> snarls (stays in tune high up)."),
                 ("GRIT", "Sample-and-bit crush texture."), ("LEV", "Output level of this terrain voice."))),
             ("concept", "VISUAL MODEL / PATH", "CONCEPTS, NOT KNOBS", K(
                 ("RATIO", "1:1 is simple; others trace knots."), ("SIZE", "Small loop = local variation."),
                 ("SIZE +", "Larger orbit visits more hills / valleys."), ("CENTER", "Moving center samples another region."),
                 ("ROT", "Angle changes the crossing pattern."), ("DRIFT", "Motion creates evolving timbre."),
                 ("TUNE", "Orbit repeats at note frequency."), ("PATH", "Height along the orbit becomes the waveform."))),
             ("concept", "SOUND / DIRECTION", "STARTING POINTS", K(
                 ("CLEAN", "SURF SINE, small SIZX / SIZY."), ("BRIGHT", "Increase either orbit dimension."),
                 ("MOVING", "Add DRFT to held notes."), ("METAL", "Experiment with RATIO + FM."),
                 ("ROUGH", "Use CHAOS / BITS + GRIT."), ("HARSH", "Increase FDBK carefully."),
                 ("LOCATION", "Sweep CNTX and CNTY by ear."), ("BALANCE", "Use LEV after aggressive settings.")))],
         first=("MOVING TERRAIN", "SURF SINE -> SIZX / SIZY small -> move CNTX / CNTY -> add DRFT"), foot="KNOB BY KNOB"),
    dict(id="spall", title="SPALL", tag="SYNTH MACHINE", logo="spall",
         sub="Sound from tiny events: clicks, dust, grains and chips, placed in time and rung through two resonators.",
         panels=[("knobs", "SYN1 / PARTICLES", "MAKE AND PLACE THE DOTS", K(
             ("TYPE", "IMP click / DUST noise / TONE grain / CHIP pulse."), ("SIZE", "Each particle: 0.05 ms tick -> 200 ms tone."),
             ("DENS", "How busy: one every 4 s -> 500 a second; 0 = one per trig."), ("GAP", "Chance a particle is skipped: sparser, broken."),
             ("EDGE", "Hard edge <- -> soft, rounded contact."), ("CLMP", "Each particle brings up to 7 fast followers: clusters."),
             ("MEM", "0 = always new; up = the phrase repeats exactly."), ("LEV", "Output level."))),
             ("knobs", "SYN2 / SURFACE", "COLOUR AND MATERIAL", K(
                 ("TUNE", "Oscillators' pitch (+/- 24 semitones)."), ("SPRD", "Six oscillators: harmonic -> stretched metal."),
                 ("ALG", "SUM all six / RING one x next / SCAN one per particle."), ("FRQA", "Resonator A pitch: every particle pings it."),
                 ("FRQB", "Resonator B pitch."), ("RING", "Ring time: 5 ms -> 5 s."),
                 ("COUP", "A feeds B: two rings become one surface."), ("MIX", "Dry particles <- -> rings."))),
             ("concept", "SOUND / DIRECTION", "STARTING POINTS", K(
                 ("STIPPLE", "IMP, EDGE up, MIX low: separate clicks."), ("4-POLE", "DUST, GAP up, CLMP some, RING mid."),
                 ("PINHOLE", "IMP, DENS low, RING long, MIX 127."), ("GLASS DUST", "DUST, high FRQA/FRQB, RING long."),
                 ("PLEE", "TONE + SCAN, SPRD low, soft EDGE."), ("CAPACITOR", "CHIP, CLMP high: sputtering."),
                 ("PHRASE", "MEM up: the pattern repeats."), ("PITCH RHYTHM", "p-lock FRQA on trigs.")))],
         first=("A FIELD OF CLICKS", "Trig a note -> DENS for busy -> GAP for space -> FRQA / FRQB for the material"), foot="KNOB BY KNOB"),
    dict(id="smear", title="SMEAR", tag="SAMPLING", logo="smear",
         sub="Continuously morph a sample from traditional tape playback into granular fragments.",
         panels=[("knobs", "SYN1 / TAPE + CLOUD", "START AT BLND 0", K(
             ("TUNE", "Pitch only (VOC, PLAY, grains); SPD stays the speed."), ("SPD", "Speed only, -4..+4; center freezes the read point."),
             ("BLND", "0 = VOC stretch; 64 = PLAY; 127 = grains."), ("SAMP", "Choose the source sample or FLEX take."),
             ("STRT", "Where the loop begins in the sample."), ("SIZE", "Loop length, 0.00-120.00 (120 = all)."),
             ("DENS", "How many grains play each second."), ("LEV", "Output volume of the machine."))),
             ("knobs", "SYN2 / GRAINS", "MORE = CLOUD-LIKE", K(
                 ("OVLP", "Length / overlap of each tiny grain."), ("SPRY", "Scatter grain start positions."),
                 ("PRND", "Randomize each grain pitch."), ("WIN", "Shape grain edges (7 windows)."),
                 ("FRZ", "Hold current position as a grain cloud."), ("-", "Not assigned on this page."),
                 ("-", "Not assigned on this page."), ("-", "Not assigned on this page."))),
             ("concept", "WHAT YOU HEAR", "PLAY <-> GRANULAR", K(
                 ("PLAY", "A continuous loop; pitch and speed apart."), ("GRAIN", "Many tiny snippets overlap."),
                 ("BLND", "Crossfade VOC, PLAY and cloud."), ("SPRY", "Fragments scatter through the buffer."),
                 ("PRND", "Individual fragments bend in pitch."), ("OVLP", "Small flecks -> longer smear."),
                 ("FRZ", "Stays on the captured moment."), ("WIN", "Smooth / sharp grain edges."))),
             ("concept", "SAMPLE WORKFLOW", "SAMPLE HANDLING", K(
                 ("SAMP", "Turn to open the project sample list."), ("[YES]", "Keep selected sample."),
                 ("[NO]", "Cancel selection."), ("[FUNC]+[YES]", "Open the +Drive browser."),
                 ("B1-B8", "FLEX buffers appear after 127."), ("LOOP", "Use STRT + SIZE to isolate a segment."),
                 ("MONO", "One voice a track: a new note takes over."), ("VOC", "BLND 0: keyframe stretch (after heavylight). SPD = time, TUNE = pitch.")))],
         first=("FROZEN CLOUD", "SAMP choose sample -> BLND from 0 upward -> DENS -> SPRY -> FRZ ON"), foot="KNOB BY KNOB"),
    dict(id="samples", title="SAMPLE MACHINES", tag="SAMPLING", logo="dt2",
         sub="A visual chooser for Digitakt II playback modes and slicing.",
         panels=[("cards", [("ONESHOT", "HITS / FREE LOOPS", "Free sample playback", "STRT = start | LEN = length | LOOP = repeat point"),
                            ("STRETCH", "BEAT MATCHING", "Tempo-locked duration", "BARS = target bars; pitch independent"),
                            ("REPITCH", "TAPE-LIKE LOOPS", "Tempo by speed", "BARS determines playback speed / pitch"),
                            ("GRID", "RHYTHMIC CHOPS", "Even sample divisions", "GRID = number of evenly-spaced slices; SLCE picks one"),
                            ("SLICE", "HAND-PLACED HITS", "Custom marker divisions", "SLCE picks a saved slice; [YES] on its page: EDIT SLICE POINTS / CREATE SLICE GRID (TR.DET = at transients) / LOCKS / CLEAR"),
                            ("FLEX", "LIVE RESAMPLING", "Live buffer playback", "BUF selects recording buffer B1-B8")]),
                 ("box", "KEYBOARD SLICES", ["On SLICE and GRID with SLCE at NOTE, each key plays its own slice from C1 up."])],
         first=("SAMPLE SELECT", "Turn SAMP -> [YES] accept / [NO] cancel • [FUNC]+[YES] +Drive • B1-B8 after slot 127"), foot="MACHINE CHOOSER", strip="SAMPLE SELECT"),
    dict(id="flex", title="FLEX / LIVE RECORDING", tag="SAMPLING", logo="flex",
         sub="A direct guide to every recording decision, from source to saved sample.",
         panels=[("steps", [("CHOOSE FLEX", "Place FLEX on a track; BUF selects buffer B1-B8. Any sample machine can also play B1-B8."),
                            ("OPEN REC", "[FUNC]+[UNISON] (the key that opens VOICE SETUP) opens the FLEX recorder. LEFT / RIGHT: REC TRIGS / REC SETUP / REC BUS."),
                            ("SOURCE / SRC", "TRK1-16 = a track; IN = input; MAIN = mix; BUS = chosen tracks (pick them on REC BUS with the [TRIG] keys)."),
                            ("R.LEN", "Recorded take length in pattern steps; [FUNC]+turn moves 16 steps."),
                            ("TRIG / Q.REC", "On REC TRIGS: [TRIG] = one-shot, [FUNC]+[TRIG] = every pass, [PAGE] = next 16 steps. Or [YES] while playing: records at the next Q.REC boundary; [NO] cancels."),
                            ("PLAY / SAVE", "FLEX plays its buffer; [FUNC]+[YES] saves the take to the next empty slot and the +Drive.")]),
                 ("kv", "RECORDER OPTIONS", [("MUTE SRC", "Keeps the source out of the mix while FLEX plays it (held 0.2 s after the note)."),
                                             ("GAIN", "Take level: 0 = the source's own level; turn down if a bus or MAIN clips."),
                                             ("ONE-SHOT TRIG", "[YES] [YES] re-arms spent one-shots."),
                                             ("CLEAR BUF", "[FUNC]+[NO] on REC SETUP, then [YES]: erases the take."),
                                             ("Q.REC", "Quantized trigless recording: 1-64 steps or the pattern length.")])],
         first=("CPU SAVER", "Record a heavy track into B1 -> FLEX note trig on step 1 plays it -> MUTE SRC ON"), foot="RECORD / RESAMPLE"),
    dict(id="fx", title="EFFECTS / PERFORMANCE", tag="GLOBAL", logo=None,
         sub="The essential controls and shortcuts, with their audible result.",
         panels=[
                 ("kv", "PLATE REVERB (FX: REVERB)", [("PRE", "Delay before tail (up to 0.3 s)"), ("DEC", "Small room -> long plate"),
                                                      ("FREQ", "Brightness shelf frequency"), ("GAIN", "Amount of treble surviving in tail"),
                                                      ("HPF / LPF", "Stock: filter the reverb"), ("MIX VOL", "Stock: reverb level")]),
                 ("kv", "PERFORMANCE", [("TRK+CLEAR", "Reset machine start values ([FUNC]+[PLAY] = CLEAR)"), ("PTN+YES", "Direct Jump ON"),
                                        ("PTN+NO", "Direct Jump OFF"), ("PTN+KEYBOARD", "Sustain held keyboard notes"),
                                        ("TRIG PAGE 2", "SLD enables slides; SLEN duration"), ("SLEN NXT", "Slide until next track trig"),
                                        ("FUNC+TURN", "FASCIA: TUNE in octaves; GEOM / SHIFT snap to 0")]),
                 ("kv", "TUNING + MONITOR", [("KB SETUP H", "Turn to select a tuning"), ("PUSH H", "Open tuning page"),
                                             ("USER 1-8", "Editable custom microtunings"), ("REC MON", "Knob C monitors input when armed"),
                                             ("MIDI", "MIDI tracks stay in 12-TET"), ("GRID / SLICE", "Slice playback is not retuned")])],
         first=None, foot="REFERENCE"),
]


def chip(k: str) -> str:
    return f'<span class="chip">{k}</span>'


def panel(p) -> str:
    kind = p[0]
    if kind in ("knobs", "concept"):
        _, title, cap, cells = p
        out = []
        for i, (n, t) in enumerate(cells):
            dead = " dead" if n == "-" else ""
            c = chip("ABCDEFGH"[i]) if kind == "knobs" else ""
            out.append(f'<div class="kc{dead}" data-s="{E((n + " " + t).lower())}">{c}<b>{E(n)}</b><p>{E(t)}</p></div>')
        cls = "kg" if kind == "knobs" else "kg cg"
        return (f'<section class="pn"><header><h3>{E(title)}</h3><span class="cap">{E(cap)}</span></header>'
                f'<div class="{cls}">{"".join(out)}</div></section>')
    if kind == "kv":
        _, title, rows = p
        r = "".join(f'<div class="kv" data-s="{E((a + " " + b).lower())}"><b>{E(a)}</b><span>{E(b)}</span></div>' for a, b in rows)
        w = " wide" if title.startswith("RECORDER") else ""
        return f'<section class="pn{w}"><header><h3>{E(title)}</h3></header><div class="kvs">{r}</div></section>'
    if kind == "steps":
        _, steps = p
        r = "".join(f'<div class="st" data-s="{E((a + " " + b).lower())}"><header><span class="num">{i + 1:02d}</span><b>{E(a)}</b></header><p>{E(b)}</p></div>'
                    for i, (a, b) in enumerate(steps))
        return f'<div class="sts wide">{r}</div>'
    if kind == "cards":
        _, cards = p
        r = "".join(f'<div class="sm" data-s="{E((a + " " + d).lower())}"><header><b>{E(a)}</b><span class="pill">{E(t)}</span></header>'
                    f'<p class="lead">{E(l)}</p><p>{E(d)}</p></div>' for a, t, l, d in cards)
        return f'<div class="sms wide">{r}</div>'
    if kind == "box":
        _, title, lines = p
        return (f'<section class="pn wide note" data-s="{E((title + " " + " ".join(lines)).lower())}"><header><h3>{E(title)}</h3></header>'
                + "".join(f"<p>{E(x)}</p>" for x in lines) + "</section>")
    raise ValueError(kind)


def page(n: int, pg) -> str:
    first = pg.get("first")
    strip = ""
    if first:
        label = pg.get("strip") or f"FIRST SOUND / {first[0]}"
        strip = f'<div class="first"><b>{E(label)}</b><p>{E(first[1])}</p></div>'
    return f"""<article class="page" id="{pg['id']}"><div class="bar"></div>
<div class="hd"><span class="brand">RIFT / QUICK REFERENCE</span><span class="pg">v{COVERS} &nbsp;/&nbsp; {n:02d}</span></div>
<div class="ttl"><div class="tl">{logo(pg.get('logo'))}<h2>{E(pg['title'])}</h2></div><span class="tag">{E(pg['tag'])}</span></div>
<p class="sub">{E(pg['sub'])}</p><hr>
<div class="pns">{"".join(panel(p) for p in pg['panels'])}</div>
{strip}
<div class="ft"><span>A-D TOP ROW &nbsp;/&nbsp; E-H BOTTOM ROW</span><span>{E(pg['foot'])} &nbsp;•&nbsp; {n:02d}</span></div></article>"""


def index_page() -> str:
    links = "".join(f'<a href="#{pg["id"]}"><b>{E(pg["title"])}</b><span>{i + 2:02d}</span></a>' for i, pg in enumerate(PAGES))
    return f"""<article class="page" id="top"><div class="bar"></div>
<div class="hd"><span class="brand">RIFT / QUICK REFERENCE</span><span class="pg">v{COVERS} &nbsp;/&nbsp; 01</span></div>
<div class="ttl"><h1>KNOBS, EXPLAINED</h1><span class="tag">START HERE</span></div>
<p class="sub">A scan-first field guide: what each encoder changes, not just what it is called. The full story is in the <a href="rift-manual.html">manual</a>.</p><hr>
<div class="idx"><div class="how">
<section class="pn"><h4>01 / HOW TO USE</h4><p>[FUNC]+[SYN] = select machine. [SYN] = next synth page.</p></section>
<section class="pn"><h4>02 / PHYSICAL GRID</h4><p>A B C D are the upper encoders; E F G H are the lower row.</p></section>
<section class="pn"><h4>03 / SOUND DESIGN</h4><p>Every card: knob name + a direct description of its audible effect.</p></section>
<section class="pn"><h4>04 / REFERENCE</h4><p>Page titles match SYN1, SYN2, SYN3, SYN4 on the hardware.</p></section>
</div><nav class="pn go"><h4>GO STRAIGHT TO...</h4>{links}</nav></div>
<input id="q" type="search" placeholder="Find a knob or tip: FRZ, DAMP, R.LEN, BOW..." aria-label="Find a knob or tip" autocomplete="off">
<div class="first"><b>READ EACH SYNTH PAGE LIKE THE HARDWARE</b><p>Top four cells = A B C D &nbsp; | &nbsp; Bottom four cells = E F G H</p></div>
<div class="ft"><span>A-D TOP ROW &nbsp;/&nbsp; E-H BOTTOM ROW</span><span>ENGINE INDEX &nbsp;•&nbsp; 01</span></div></article>"""


CSS = """
:root{color-scheme:dark;--bg:#0b0e10;--pg:#0f1315;--pn:#1a2025;--card:#222a30;--line:#2d363c;--ink:#eef0ee;--dim:#a9b2b5;--teal:#6fc7b4;--gold:#e2c27a;--chip:#33464a}
*{box-sizing:border-box;min-width:0}
html{scroll-padding-top:12px}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.45 'IBM Plex Sans','Segoe UI',system-ui,sans-serif;overflow-x:clip}
a{color:var(--teal)}
main{max-width:1240px;margin:0 auto;padding:18px max(12px,2vw) 60px;display:grid;gap:22px}
.page{position:relative;background:var(--pg);border:1px solid #1c2226;border-radius:6px;padding:26px clamp(16px,3vw,40px) 18px;overflow:hidden}
.bar{position:absolute;left:0;right:0;top:0;height:6px;background:var(--teal)}
.hd{display:flex;justify-content:space-between;gap:12px;font:700 13px 'IBM Plex Mono',ui-monospace,monospace;letter-spacing:.06em}
.brand{color:var(--teal)}.pg{color:var(--dim);font-weight:400}
.ttl{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-top:14px;flex-wrap:wrap}
.tl{display:flex;align-items:center;gap:16px}
h1,h2{font-size:clamp(28px,4vw,40px);line-height:1.05;margin:0;letter-spacing:.02em;font-weight:800}
.logo{image-rendering:pixelated;flex:none;background:#000;border:1px solid var(--line);border-radius:6px;padding:4px;width:100px;height:72px}
.tag{font:700 12px 'IBM Plex Mono',monospace;letter-spacing:.08em;color:var(--gold)}
.sub{color:var(--dim);margin:8px 0 14px;font-size:14px}
hr{border:0;border-top:1px solid var(--line);margin:0 0 22px}
.pns{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.pn{background:var(--pn);border:1px solid var(--line);border-radius:10px;padding:14px}
.pn header{display:flex;justify-content:space-between;align-items:baseline;gap:10px;margin-bottom:12px;flex-wrap:wrap}
.pn h3{margin:0;font-size:15px;letter-spacing:.05em;color:var(--teal);font-weight:800}
.cap{font:11px 'IBM Plex Mono',monospace;color:var(--dim);letter-spacing:.06em;text-align:right}
.kg{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
.kc{background:var(--card);border-radius:6px;padding:9px 9px 10px;min-height:82px}
.kc b{font:800 14px 'IBM Plex Sans',sans-serif;letter-spacing:.03em;vertical-align:middle}
.kc p{margin:7px 0 0;font-size:12.5px;line-height:1.35;color:#c9d0d2}
.chip{display:inline-block;min-width:21px;text-align:center;background:var(--chip);color:var(--teal);font:700 12px 'IBM Plex Mono',monospace;border-radius:3px;padding:2px 5px;margin-right:8px;vertical-align:middle}
.cg .kc{border-left:3px solid var(--gold)}
.cg .kc b{color:var(--gold)}
.kc.dead{opacity:.55}
.kvs{display:grid;gap:9px}
.kv{display:grid;grid-template-columns:minmax(90px,30%) minmax(0,1fr);gap:12px;font-size:13px}
.kv b{color:var(--gold);font:700 12px 'IBM Plex Mono',monospace;letter-spacing:.04em;padding-top:1px}
.kv span{color:#d7dcdd}
.wide{grid-column:1/-1}
.sts{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.st,.sm{background:var(--pn);border:1px solid var(--line);border-radius:10px;padding:14px 16px;min-height:120px}
.st header{display:flex;gap:10px;align-items:center}
.num{background:var(--chip);color:var(--gold);font:700 11px 'IBM Plex Mono',monospace;border-radius:3px;padding:3px 6px}
.st b{font-size:15px;letter-spacing:.04em}
.st p,.sm p{margin:10px 0 0;font-size:13.5px;color:#cdd3d5}
.sms{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.sm header{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap}
.sm header b{font-size:20px;letter-spacing:.03em}
.pill{background:var(--chip);color:var(--gold);font:700 10.5px 'IBM Plex Mono',monospace;border-radius:4px;padding:4px 8px;letter-spacing:.05em}
.sm .lead{color:var(--teal);font-weight:700;font-size:15px}
.note p{margin:6px 0 0;font-size:13.5px;color:#d0d6d8}
.first{background:#263035;border-radius:8px;padding:12px 14px;margin-top:14px}
.first b{color:var(--gold);font:700 12.5px 'IBM Plex Mono',monospace;letter-spacing:.06em}
.first p{margin:6px 0 0;font-size:14px}
.ft{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;border-top:1px solid var(--line);margin-top:20px;padding-top:10px;font:11px 'IBM Plex Mono',monospace;letter-spacing:.06em;color:var(--dim)}
.ft span:first-child{color:var(--teal)}
.idx{display:grid;grid-template-columns:minmax(0,1.85fr) minmax(0,1fr);gap:16px}
.how{display:grid;gap:12px}
.how h4,.go h4{margin:0 0 8px;color:var(--gold);font-size:13px;letter-spacing:.05em}
.how p{margin:0;font-size:13.5px}
.go h4{color:var(--teal);font-size:15px}
.go a{display:flex;justify-content:space-between;padding:6px 2px;text-decoration:none;color:var(--ink);border-radius:4px}
.go a span{color:var(--gold);font:12px 'IBM Plex Mono',monospace}
.go a:hover,.go a:focus-visible{background:var(--card)}
#q{display:block;width:100%;margin-top:16px;font:16px 'IBM Plex Mono',monospace;background:var(--pn);color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:11px 12px;min-height:44px}
#q:focus{outline:2px solid var(--teal);outline-offset:1px}
.hit{outline:2px solid var(--gold);outline-offset:-2px}
.gone{display:none!important}
@media(max-width:820px){.pns,.idx,.sms{grid-template-columns:minmax(0,1fr)}.sts{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:520px){.kg{grid-template-columns:repeat(2,minmax(0,1fr))}.sts{grid-template-columns:minmax(0,1fr)}.logo{width:72px;height:52px}.kv{grid-template-columns:minmax(0,1fr);gap:2px}}
"""

JS = """<script>
{
const q=document.getElementById('q');
const pages=[...document.querySelectorAll('main .page')].slice(1);
const run=()=>{const v=q.value.trim().toLowerCase();
for(const el of document.querySelectorAll('[data-s]'))el.classList.toggle('hit',!!v&&el.dataset.s.includes(v));
for(const p of pages){if(!v){p.classList.remove('gone');continue;}
const any=[...p.querySelectorAll('[data-s]')].some(e=>e.dataset.s.includes(v))||p.querySelector('h2').textContent.toLowerCase().includes(v);
p.classList.toggle('gone',!any);}};
q.addEventListener('input',run);
}
</script>"""


def build() -> str:
    body = index_page() + "".join(page(i + 2, pg) for i, pg in enumerate(PAGES))
    return f"""<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>RIFT quick guide</title>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;700&family=IBM+Plex+Sans:wght@400;700;800&display=swap" rel="stylesheet">
<style>{CSS}.pdfbtn{{position:fixed;top:10px;right:14px;z-index:20;font:600 13px/1 'Space Grotesk',ui-sans-serif,system-ui,sans-serif;letter-spacing:.04em;color:#fff;background:#8a2a3c;border:1px solid #b04a5c;border-radius:8px;padding:9px 13px;text-decoration:none}}.pdfbtn:hover{{background:#a0344a}}@media print{{.pdfbtn{{display:none}}}}</style></head><body><a class="pdfbtn" href="rift-quick.pdf" download title="The quick guide as one PDF">Download PDF</a><main>{body}
<p class="sub" style="text-align:center">Unofficial: not made or supported by Elektron. Everything else (p-locks, LFOs, kits, MIDI) works as on the stock Digitone II. <a href="rift-manual.html">Full manual</a>.</p>
</main>{JS}</body></html>
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
