# SILT on the DSP: cost plan (2026-11-17)

The audition model (`work/silt/silt_model.py`, the one the owner approved by ear: SNAP 70)
runs per 32-sample block like the DN2 does, so its structure maps onto the SHARC as it is.
This is the plan for keeping it inside the frame before any SHARC code is written.

## The budget

- Frame: 666,667 cycles. The silent stock frame: about 416,000 (62 %), `docs/timing-model.md`.
- The guard keeps our voices inside 0.8 of the frame: about **117,000 cycles for all of
  RIFT's voices together** (estimate: instructions + 4 x L2 + 10 x DDR accesses).
- For scale (`docs/dsp-cost.md`): a P-I drum about 21-33k, VO-6 about 48k, a heavy FASCIA
  voice at its attack about 51k instructions before its memory (two of those and the guard
  starts leaving voices out: the testers' "3-4 voices max").

## SILT's cost, per voice, per block (estimate from the model's operations)

| part | per sample | per block (x32) | DDR per block |
|---|---|---|---|
| shared: noise, strike pulse, body (4 modes), FORM (SVF), follower, AMP, soft clip | ~70 ins | ~2,240 | 0 |
| FIBER: two interpolated reads, the loop filter, the bow table (one reciprocal), two writes, the 4-pole bridge high-pass | ~75 ins, 6 DDR | ~2,400 | 192 |
| SKIN / FLUID: one read, 4 all-passes, soft clip, SVF, write | ~60 ins, 3 DDR | ~1,900 | 96 |
| SILT (particles): 6 modes, the particle test | ~55 ins | ~1,760 | 0 |
| one secondary filament: read (2), its bow table, write (1) | ~32 ins, 3 DDR | ~1,020 | 96 |
| per-block coefficients (pitch, 4 body modes, 6 modes, SVFs, the filaments' pitches) | | ~3,500 | 0 |

Worst case, FIBER in MASS-8 with QUAL DEEP (8 filaments):
~2,240 + 2,400 + 8 x 1,020 + 3,500 = **~16,300 instructions**, ~960 DDR accesses
(~9,600 cycles), a few hundred L2: **about 27,000 cycles, 4 % of the frame**.
QUAL NORMAL (4 filaments) is about 19,000; SOLO about 10,000.

So SILT is a P-I-drum-sized machine, not a FASCIA-sized one. Four DEEP voices fit in the
budget with room; eight do not.

## Memory

A voice holds a 2048-sample waveguide pair (FIBER: bridge and nut) and 8 x 1024 filament
loops: 48 KB in float32. That is DDR (as the sample machines' and ORGAN's tables are). The
delay pointers advance one sample at a time, so each block's reads are 32 consecutive words
per line: the read can be one burst per line per block into an L1 scratch, then L1 reads
(the plan below, item 3), which would take most of the DDR count away.

## Where the lines live (decided 2026-11-17)

- **DDR, 48 KB a slot, every slot:** `SILT_DELAY_DDR = 0x82400000`, slot t at
  `+ t x 0xC000` (16 x 48 KB = 768 KB, to 0x824C0000). It sits above the Machinedrum's
  P-I delay lines (0x82200000, 128 KB) and below the sample pool (0x84000000), in the
  span `docs/w5-tables.md` measured clear of the stock's init (the tables live at
  0x81000000 for the same reason). The M5 gate's "every span we add reads back, after init"
  covers it. Every slot can be SILT, so no bank allocation: the cap is a count.
- **Garbage at power-on:** 768 KB of zeros cannot ride in the DSP image (the upload buffer's
  1 MiB, unpacked 947 KB used), and clearing a voice's lines at a note costs up to 12,288
  DDR writes in one block. Instead each line carries a **written count** that saturates at
  its length: a read further back than the count returns 0. It is reset only when the slot
  becomes SILT (the walk's type change) or the output guard wipes the voice, never at a
  note, so a retrigger rings on through the old vibration exactly as the model's does. One
  compare a read.

## Guardrails (the owner's request for every engine, applied to SILT from its first build)

1. **A voice cap:** at most 4 SILT voices sound at once across the tracks; a fifth note
   steals the oldest SILT voice (with the 32-sample fade every machine of ours uses).
2. **QUAL DEEP is 6 filaments, not 8**, unless the owner hears a difference worth 2,000
   instructions a voice (to be auditioned: DEEP-8 against DEEP-6 on POLYMORPHIA and
   SWELL).
3. **Block-burst delay reads** (L1 scratch per line per block), so DDR is 3 bursts a voice,
   not ~960 single accesses.
4. **Coefficients on alternate blocks** for the slow ones (the body's and modes' cos/sin,
   the filaments' pitches): their controls are read every block, but the values they feed
   move at the speed of a knob (the FASCIA approach).
5. **Graceful degradation:** when the guard's clock says the frame is full, a SILT voice
   first drops its filaments to NORMAL (4), then SOLO, before it is left out.
6. **The gate:** the runner's cost step covers SILT (worst patch, 4 voices, every control
   moving) and the stress step must stay under 0.8 of the frame with stock machines on the
   other tracks; a negative control (the cap disabled, 8 voices) must exceed it.

## The port (the same exactness chain as ORGAN and FASCIA)

1. `src/dnfw/silt/live.py`: the model in float32 with the DSP's own primitives (recip,
   exp2f, sin_turns, the soft clip), compared with the audition model (spectra and level,
   not bit-exact: the primitives differ). Sound choices go to the owner's ear first.
2. `src/dnfw/silt/program.py`: the SHARC DSL, bit-exact to live.py.
3. `machines.py`: type 20, four pages (MATTER, CONTACT, STRUCTURE, CONFIG), the choices on
   page 4.
4. Gates: unit tests (live = program = SHARC), the ColdFire step (MACHINE SEL, pages, save
   and load), the SHARC runner part, the cost and stress parts with the voice cap.
