# DSP time and memory, release by release

Kept by the release review (`docs/QA.md`). Cycles a block (32 samples) on the unit's cost model:
instructions + 0.95 x (4 x L2 + 10 x DDR accesses), one voice sounding, less an idle frame
(`scripts/sharc_waverider_m5.py --steps rcost`). The frame is 666,667 cycles; an idle frame is
about 416,000 on the unit. A row is written only from a measurement, with its source.

## One voice, worst block

| release | FASCIA bell (strike) | CONTOUR 1 / 2 / 4 steps | SPALL dense | ORGAN every rank | DIGIDRUM | LIGATURE | SILT | SMEAR GRN | source |
|---|---|---|---|---|---|---|---|---|---|
| v0.27 tree (not released) | 87,800 (112,800) | 25,400 / 44,600 / 82,000 | 27,500 | 26,200 | 27,900 | 39,400 | 15,400 to 35,700 | about 70,000 | the build session's run, 2026-11-25; not re-measured by a review |
| v0.28 (frozen 66bffc8) | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | the review of v0.28, 2026-11-26: no bench in its session, so no cell is filled. The build session's own figures for this release are in its commits (the master reverb 43,263 -> 28,581 cycles a block, 86865c2; ONESHOT and GRID 30,800 at worst, SMEAR 21,000 to 27,000, ee7b1e7) and were not measured again |
| v0.29 (frozen 073a80f) | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | the review of v0.29, 2026-11-27: no SHARC emulator in its session. The build session's own figures are in its commits (the master reverb 28,581 -> 26,575 cycles a block, cc9107b; DIGIDRUM struck, by type: BD 27,977, SD BASIC 25,046, SD VINTAGE 48,798, CP 39,751, CY 39,711, PC 23,132, 9a19abe) and were not measured again |
| v0.30 (frozen 0dc29eb) | not measured | not measured | not measured | not measured | not measured | not measured | not measured | not measured | the review of v0.30, 2026-11-28: no SHARC emulator in its session. The build session gives no new cycle figure for this release in its commits; the mono scan's size in the DSL's steps is in `REVIEW-v0.30.md` |

A slot with no note, same run: FASCIA 900, ORGAN 860, CONTOUR 1,570, SPALL 1,640, LIGATURE
2,560 instructions.

## Bytes to spare

| release | DSP upload (of 1,048,575 unpacked) | 2 MiB image | source |
|---|---|---|---|
| v0.27 tree (not released) | about 181 before FASCIA's walk shared the guard code, which gave about 2 KB back | reported as about 3.2 KB and as about 800 bytes the same day | the build session's notes, 2026-11-25; to be measured at the first review |
| v0.27 (3118908) | 1,951 (1,046,624 unpacked) | not measured | the v0.28 review's addendum, 2026-11-26: `dnfw mods apply` on the stock OS 1.11 gave the released file (sha256 3b987e6c...); `safety.preflight`'s DSP size line |
| v0.28 (frozen 66bffc8) | 5,949 (1,042,626 unpacked) | not measured | the same, on this tree's build (sha256 a69ae35d..., not gated here). MAIN OS unpacks to 3,495,576 bytes, 660 more than v0.27's |
| v0.27 (3118908) | 1,951 | 796 to spare (2,096,356 of 2,097,152) | the review of v0.29, 2026-11-27: the same build again (sha256 3b987e6c..., the released file); `safety.preflight`'s image line |
| v0.28 (9b5e2c3, `rc/v0.28` as gated) | 5,889 (1,042,686 unpacked) | 1,604 to spare (2,095,548) | the same, on this tree's build (sha256 9572904e..., not gated here) |
| v0.29 (frozen 073a80f) | 5,137 (1,043,438 unpacked) | 1,806 to spare (2,095,346) | the same (sha256 7ce19eb6..., not gated here) |
| v0.30 (frozen 0dc29eb) | 5,013 (1,043,562 unpacked) | 1,200 to spare (2,095,952) | the review of v0.30, 2026-11-28: `dnfw mods apply` on the stock OS 1.11 (sha256 c786acf4..., not gated here); `safety.preflight`'s lines |

## Our DSP code as assembled

The bytes of each stage's parcels in `src/dnfw/waverider/sharc_code.json` (`object_parcels_be`), counted from the
committed file. It is the code before packing, not the room left in the upload: it shows which stage grew.

| release | perc | smp | fascia | smear | mverb | every stage | source |
|---|---|---|---|---|---|---|---|
| v0.27 (3118908) | 9,568 | 23,642 | 145,210 | 6,104 | 4,734 | 190,526 | counted by the review of v0.28, 2026-11-26 |
| v0.28 (frozen 66bffc8) | 9,202 | 23,682 | 142,584 | 6,144 | 3,668 | 186,548 | the same count |
| v0.28 (9b5e2c3) | 9,202 | 23,722 | 142,576 | 6,172 | 3,668 | 186,608 | counted by the review of v0.29, 2026-11-27 |
| v0.29 (frozen 073a80f) | 9,202 | 23,746 | 142,708 | 6,724 | 3,712 | 187,360 | the same count |
| v0.30 (frozen 0dc29eb) | 9,202 | 23,746 | 142,708 | 6,848 | 3,712 | 187,484 | counted by the review of v0.30, 2026-11-28 |

The ColdFire's C chunk (`c_chunk` in `src/dnfw/mods/waverider_code.json`): 216,272 bytes at v0.27, 217,152 at
v0.28; the 192-byte glass chunk is gone.
216,416 at v0.29 (RUBBER's page code out).
217,532 at v0.30 (+1,116: the buffers' overviews, the step lag, keys first, TEMPO + YES, the leaner ISR hooks).

The sample machines' L2 span (24,576 bytes, `dsp.SMP_L2_SPAN`) at v0.29: smp 23,746 and pvmix's room 744, 86 bytes
left (computed from the count above). At v0.30 the same: smp.asm and pvmix did not change.

## Known places to give time back (2026-11-25)

- **CONTOUR**: a step is about 590 cycles (4 or 5 sines, 3 wraps, the surfaces). A table sine,
  or two sines at once on the SHARC's second element set.
- **FASCIA**: coefficients computed every block are about 30 % of a voice, the modes per sample
  about 33 %, the exciters about 16 %.
- **ORGAN, DIGIDRUM**: not yet profiled for this.
- **The master reverb** (2026-11-26, the review of v0.28): 42 line addresses are computed for every sample
  (counted in `mverb.asm`), 38 of them at a delay that does not change within a block. See
  `REVIEW-v0.28.md`, "Optimizations".
- **SMEAR's mono scan** (2026-11-27, the review of v0.29): it runs on every block, 386 steps of its program with
  no SMEAR track (the DSL's steps, not the unit's instructions); one test of the frame's trigger word would skip
  it on every block without a note. See `REVIEW-v0.29.md`, "Optimizations".
- **SMEAR's mono scan, again** (2026-11-28, the review of v0.30): the rule on state compares every pair of voices
  on every block a SMEAR voice is on: 605 steps of its program with one track sounding, 1,666 with four, 8,338
  with sixteen, no note played (v0.29: 387, 390, 402; the DSL's steps, not the unit's instructions). Fades that
  could not run kept in FADE until they do would let the scan run on trigger blocks only. See `REVIEW-v0.30.md`.
