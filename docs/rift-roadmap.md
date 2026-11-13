# RIFT roadmap: engines and effects after v0.1

The owner's wish list (2026-11-12 and 2026-11-13), with what is known so far and what must be
researched before each is designed. Nothing here is started before v0.1 (FASCIA) ships.
Every item is built to come out cleanly (one constant or one commit), gated like everything
else, and any sound choice goes to the owner's ear first.

## 1. A per-track FX platform

The base for most of the effects below: an effect slot per track, in the voice's chain, that
our own effects can be loaded into.

- Reference: the Overtone DN2 mod's way of adding effects (its source or docs are still
  needed from the owner).
- Research: where in the stock per-track chain (after the filter, before the amp, or after
  the amp) an insert can sit; its DSP cost per track; how its parameters reach the screen
  and p-locks (records, as FASCIA's do) without taking slots from the machines.

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

## 2. A function-generator looping envelope

Maths-style: attack and decay with exponential to logarithmic curves, looping (a cycling
envelope, an LFO with shape) or one-shot. Research: whether it can be a modulation source on
the stock LFO/envelope routing, or lives inside our own machines and effects first.

## 3. An LPG-style filter type

A new filter type beside the stock ones. FASCIA already has an LPG (its model is the
starting point). Research: how the DN2's per-track filter types are chosen and run on the DSP,
and whether a new type can be added there without touching the stock types.

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

## 6. Maybe

- **Syntakt digital drum machines** inside one PERC-style machine, its TYPE knob p-lockable to
  pick a different machine per step, as the DN2 mk2 mod's PERC did with the Machinedrum's.
