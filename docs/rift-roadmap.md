# RIFT roadmap: engines and effects after v0.1

The owner's wish list (2026-11-12 and 2026-11-13), with what is known so far and what must be
researched before each is designed. Nothing here is started before v0.1 (FASCIA) ships.
Every item is built to come out cleanly (one constant or one commit), gated like everything
else, and any sound choice goes to the owner's ear first.

## Status (2026-11-13, branch fx-platform)

- **FX platform:** designed (`docs/fx-platform.md`); the DSP insert stage built and gated; the
  ColdFire side (LFO4's side table merged into waverider, the INSERT page, the link's insert
  words) next.
- **Reference models and auditions, for the owner's ear** (`src/dnfw/fx`, `scripts/fx_audition.py`):
  RESON (ported from Viscera), RSNTR (P-6 resonator), WARP (Frequency Warper), CHRONO (Chrono
  Pitch), the LPG filter type, FUNC (the looping function generator). 40 tests.
- **capicola:** read and costed (about 4,000-6,500 instructions a voice a block on the DT2, a
  tenth of a FASCIA voice). heavylight asked that his code stay private until his green light, and
  this repository is public: the notes are in the private bench (RESEARCH-capicola.md); nothing
  derived from it comes here before that.
- **Nebulae:** the pedal's vocoder does a whole 2048-point frame (3 FFTs) every 512 samples; on the
  SHARC that work must be spread over the hop's 16 blocks (a design point before any model).

## 1. A per-track FX platform

The base for most of the effects below: an insert effect per track, its own place in the
voice's chain. **Not** a filter type: the DN2 mk2 mod's PING, grain and frequency-shift
effects rode the filter slot; RIFT's effects do not (owner, 2026-11-13).

- **Reference: Overtone** (github.com/complex-ping/overtone, AGPL). Its repository holds the
  patcher and a pack of bytes, not the insert's source, so it is a reference for the design,
  not code to reuse. Its design: [FX] page 1 gains **M.SEL** (which insert: FLNG, PHSR, CHOR,
  REVB) and **MOD** (dry/wet), both p-lockable, so one trig can switch effect; page 2 is the
  insert's own eight knobs; a route knob puts it **PRE FLTR** (before the filter, in stereo,
  the track then takes two voices per note) or **POST FLTR** (after the pan); a third page
  moves the stock bit reduction and overdrive before or after the filter. LFOs and its
  envelope followers modulate inserts; slides reach them. SETTINGS > SYSTEM > DSP LOAD shows
  the engine's load.
- Research: the records its pages use (the FX page's spare places), the DSP cost per track,
  the stereo PRE FLTR path's two voices, and how it keeps the shared delay/reverb/chorus intact.

Effects for it, in no fixed order:

- **RESON**: the eight-band resonant fixed filterbank / vocoder / ping engine from the Viscera
  (M-VAVE FM1) design, with its LIQUID macro, transient-triggered pings and the particle ideas
  (DUST first, then DROPLET, MIGRATE). Its design brief is in the conversation of 2026-11-12.
- **A Roland P-6-style resonator.** Research: what the P-6's resonator does (a tuned comb/
  resonator per pad), from its manual and by ear.
- **The Tonverk frequency shifter.** The DN2 mk2 mod had a shifter (SHFT, removed in v0.27);
  its code is a starting point, matched against the Tonverk manual (in the project).
- **The Tonverk granular pitch effect.** Research: the Tonverk manual's description, then a
  model to the owner's ear.
- (Tonverk OS 1.4.1's update, given 2026-11-13: its root and apps filesystems are encrypted
  (no squashfs header, 8.0 bits a byte), so both Tonverk ports are made from the manual and by
  ear, not from its code.)

## 2. A function-generator looping envelope

Maths-style: attack and decay with exponential to logarithmic curves, looping (a cycling
envelope, an LFO with shape) or one-shot. Research: whether it can be a modulation source on
the stock LFO/envelope routing, or lives inside our own machines and effects first.

## 3. An LPG-style filter type

A real new filter type beside the stock ones (the mod already added filter types, so the
mechanism is known). FASCIA's LPG model is the starting point.

## 4. A Nebulae-style phase vocoder / granular machine

After Qu-Bit's Nebulae V2 and the owner's own mono port of it to a guitar pedal:

- **Sources.** github.com/Qu-Bit-Electronix/QB_Nebulae_V2 (MIT; the engine is the Csound
  instrument `Code/instr/a_granularlooper.instr`; the module itself runs Csound on a
  Raspberry Pi compute module, not a Daisy) and github.com/De-Pattern/Nebulae-Granular_Looper_Pedal
  (MIT; a transcription of that instrument to a Daisy Seed3 in a Terrarium, mono, with built-in
  LFOs; validated against a Python reference).
- **The pedal's engine** (src/nebulae_dsp.*): a 120 s live buffer; a phase vocoder (Csound's
  `mincer`: FFT 2048, 4x overlap, hop 512, phase-locked) and a granular voice (`partikkel`,
  up to 10 grains, spray, pitch randomness, RMS limiter 0.20) in parallel off the same
  buffer, a constant-power BLEND between them; LFO 1 on read position (and optionally blend),
  LFO 2 on loop length (or the bandpass); a frequency shifter and bandpass after.
- **On RIFT**: the capicola stretch (heavylight's, authorised) as the time-stretch core,
  beside a granular voice; the live buffer is FLEX's (or a sample); stereo, per the owner's
  stereo plan; the pedal's LFOs become the DN2's own (LFOs, p-locks, slides).
- **Research first**: capicola's and an FFT-2048 vocoder's cost on the SHARC (the ADSP-2156x
  has hardware FFT and FIR accelerators; whether the stock engine leaves them free); how many
  such voices fit; the buffer in DDR; the controls on pages of 8.

## 5. Already planned (2026-11-12)

- A capicola-stretch single-sample machine (DT2-style) with the Viscera PUTTY ideas.
- A single FLEX machine.
- Stereo through the whole chain for both: stereo samples as one L/R sample, stereo
  resampling and recording.
- The same sample import tool as the DN2 mk2 mod.

## 6. Ideas to weigh

- **Running FASCIA at a lower internal rate** (a tester, JEK, 2026-11-13: Mutable Instruments
  ran Rings' resonator at 32 kHz in Elements to make room). 32 kHz saves about a third of
  FASCIA's per-sample work, but costs a resampler on its output, moves the Nyquist to 16 kHz
  (the bright partials of the glass, tick and bell patches sit up there), and changes the
  approved sound, so it is weighed only after the voice count is measured, and only by ear.

## 7. Maybe

- **Syntakt digital drum machines** inside one PERC-style machine, its TYPE knob p-lockable to
  pick a different machine per step, as the DN2 mk2 mod's PERC did with the Machinedrum's.
