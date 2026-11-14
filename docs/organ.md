# ORGAN: Ravel's pipe organ as a RIFT machine

**Owner, 2026-11-14:** RIFT is a completely custom engine; its second original machine is ORGAN,
from the owner's own Ravel firmware for the M-VAVE FM-1 ("they sound great there"), then SILT.

The source is Ravel's (github.com/De-Pattern/Ravel_FM1, the owner's, GPL-3.0): `organ_note` and
`organ_render` in `firmware/app/rv_synth.c`, the pipes in `rv_organ.h` (from `tools/gen_organ.py`),
the knobs in `rv_params.c` (SRC_ORGAN), the presets in `rv_presets.c`. Its own description is the
"Ravel synth engines: ORGAN, LOGIC and HARMONIC" document (2026-11-14).

## The chain of exactness

1. **Done:** `src/dnfw/organ/ref.py`, float32, Ravel's C operation for operation with Ravel's
   own maths (fm_exp2f, fm_sin_turns, fm_tanf, fm_sqrtf, xorshift32, the TPT SVF). It equals the C
   compiled at 48 kHz and 32-sample blocks **bit for bit** on Ravel's five presets, every knob at
   127 and a low 16' (`scripts/organ_ref.py` builds the C and records its hashes;
   `test/test_organ_ref.py`).
2. `src/dnfw/organ/live.py`: the same with the SHARC's arithmetic. The SHARC has no exact
   divide (FASCIA's `recip`: a seed and three Newton steps, about 4e-8 relative), and Ravel
   divides about a dozen times a block (never per sample: `-age / sp`, the room, the level's
   square root, the SVF's coefficients, tan's sin / cos). live.py is held to ref.py within a
   tolerance (a difference far below hearing, measured and fixed in its test).
3. The SHARC program (`src/dnfw/organ/program.py`, the perc DSL, as FASCIA's), bit-exact to
   `live.py` in run mode; then on the SHARC runner, beside FASCIA and the sample machines.
4. The machine on the ColdFire.

So the DN2's ORGAN is the FM-1's at 48 kHz, to the last bits of a few per-block coefficients (Ravel runs at 44.1 kHz and 128-sample blocks: the
per-sample constants Ravel's notes list, the chiff's 0.9992 and the air's 0.08, are kept as they
are, so the chiff is about 9 % shorter and the air a little brighter, as the notes say; the
speech, wind and tremulant run per 32-sample block, smoother than per 128).

## The machine

- **Type 19** (FASCIA is 18): a new type, not one of PERC's or the Monomachine's freed numbers,
  so an old DN2 mk2 project's PERC track still opens as FM Tone, never as an organ.
- **Two pages of eight**, Ravel's sixteen knobs in Ravel's order:
  - SYN1 RANKS: STOP, 16', 8', 4', 2 2/3', 2', 1 3/5', 1'
  - SYN2 PIPES: CHIFF, SPEECH, SPREAD, AIR, WIND, TREMLNT, TREM RT, CELESTE
- **Records: FASCIA's.** FASCIA writes its own defaults at MACHINE SEL (`fsc_default`,
  `rec.c`), and the names, the LFO list and the choices are per machine (`page.c`, `fmt.c`), so a
  record is free to serve two machines: a track is one or the other. STOP rides a choice record
  (5 of FASCIA's choices are 0..100 or 0..120 records), the fifteen others continuous 0..0x7f00
  ones. No new record, no stock record changed.
- What generalises: FASCIA's single-machine tables (`fsc_rid`, `fsc_default`, `fsc_nolfo`, the
  quantiser, the names) become one table per machine, keyed by type.
- Defaults are Ravel's (STOP NACHTHORN, 8' 110, 4' 70, 2' 40, CHIFF 40, SPEECH 50, SPREAD 40,
  AIR 25, WIND 30, TREM RT 60, the rest 0). The presets (INFINITE, PLENUM, VOX CELESTE,
  FLUTE 4', TROMPETTE) are sounds, with Ravel's reverb sends on the DN2's reverb: the church is
  the reverb, as on the FM-1.
- Ravel's per-engine trim (0.519) goes on the program's output, so ORGAN sits at FASCIA's level.

## Cost

Per voice and block: one or two interpolated table reads per sample for each rank sounding (8
at most), one SVF tick and two noise samples per sample; the rank pitches, speech and table
choice once a block. Measured on the SHARC runner before shipping; expected well under a FASCIA
voice (about 70,000 cycles a block at its median).

## The gate

SHARC runner `organ` (bit-exact to `live.py` on the five presets and the extreme case, per
voice, beside FASCIA and ONESHOT voices), `ostress` (the stress scenarios: the guard holds, the
sample voices first), `ogarbage` (random state: bounded, no NaN past the voice). ColdFire:
`organ` (MACHINE SEL, both pages' names, STOP's five choices, defaults, p-locks, SAVE/LOAD, a
sound copy, a type-19 sound opened on a build without ORGAN plays as FM Tone).
