# LIGATURE: WEFT's block voice as a RIFT machine (type 21)

Owner, 2026-11-16: "creating one voice from small building blocks ... like the core concept from BEAD."
The design is in the project doc `claude/ligature-design.md` (v2, a block patcher). This file is
what v1 (RIFT v0.7) built of it.

## v1: fixed wirings, live settings

- **Twelve blocks a patch**, each doing one thing to its inputs A and B: WEFT's kernels (Ravel's
  `rv_weft.c`), 22 of them: PHASE WAVE SLOPE CYCLE SLEW LP BP HP ADD MULT MIX FOLD COMP XOR FLIP
  HOLD SKIN BAR SAT RUNGLER IMPULSE CREASE. Sources: PITCH GATE TRIG VEL NOISE LFO1 LFO2.
- **PATCH** picks one of 13 of WEFT's factory patches that use those blocks: INIT, SYNC LD,
  DX BELL, PH DIST, DRONE, TANGLE, SH BLIP, TOMSKIN, PLONK, MANGRVE, SPLIT, CREASE, BENJOLN.
- **Pages 2-4**: the twelve blocks' two settings each, as offsets from the patch's own value
  (64, shown 0: the patch as WEFT made it), so a PATCH change keeps sounding as designed and a
  p-lock moves a setting from there. A block a patch does not use: its knobs do nothing.
- **Page 1**: PATCH, TUNE (+-24 semitones), FINE (+-50 cents), LFO1 and LFO2 (0.05 .. 25 Hz, the
  LFO sources), VSNS (velocity on the level), DRIV (into a soft clip), LEVL.
- **Not yet** (the design's later steps): the PATCH page with the 12-tile grid and wiring editing,
  per-project wiring lists on the +Drive, `.weft.json`, the DELAY/STRING family, ABRADE, COLLIDE
  and TENSION.

## The block run (one decision to revisit)

Each block runs a whole block of 32 samples in turn, 1 to 12, into its own buffer in the voice. A
cord from an earlier block reads this block's samples; a cord from the block itself or a later one
reads what it made the block before: **32 samples late (0.67 ms), where WEFT is one sample late.**
Feedback patches (TANGLE, BENJOLIN) sound a little different from Ravel's; the DSP cost is far
lower (no per-sample dispatch). To ask the owner.

## The chain of exactness

`live.py` (float32, FASCIA's recip, Ravel's leaves) is the contract; `program.py`'s run mode is it
bit for bit (`test_ligature_program`: every patch with every setting moving, extreme panels, a
patch change mid-note, a release to rest); the SHARC runner's `ligature` part holds the assembled
code to the run mode, beside FASCIA and two at once, with a negative control; `lstress` runs sixteen
voices under the guard.

## Memory

Its voice in the slot's FASCIA state (L2): 14 words, 12 blocks x 24 words, 12 x 32 samples
(2,700 bytes of 3,968). The block's words and the arrays `ain`, `bin`, `tg`, `nz`, `mc` in FASCIA's
transient scratch (L1). The patch table, the knobs' records and the ratios in DDR at
`LIG_TABLES_DDR` 0x81227000 (`ddr.json`, written by `scripts/gen_fascia_asm.py`).
