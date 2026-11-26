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

A slot with no note, same run: FASCIA 900, ORGAN 860, CONTOUR 1,570, SPALL 1,640, LIGATURE
2,560 instructions.

## Bytes to spare

| release | DSP upload (of 1,048,575 unpacked) | 2 MiB image | source |
|---|---|---|---|
| v0.27 tree (not released) | about 181 before FASCIA's walk shared the guard code, which gave about 2 KB back | reported as about 3.2 KB and as about 800 bytes the same day | the build session's notes, 2026-11-25; to be measured at the first review |
| v0.27 (3118908) | 1,951 (1,046,624 unpacked) | not measured | the v0.28 review's addendum, 2026-11-26: `dnfw mods apply` on the stock OS 1.11 gave the released file (sha256 3b987e6c...); `safety.preflight`'s DSP size line |
| v0.28 (frozen 66bffc8) | 5,949 (1,042,626 unpacked) | not measured | the same, on this tree's build (sha256 a69ae35d..., not gated here). MAIN OS unpacks to 3,495,576 bytes, 660 more than v0.27's |

## Our DSP code as assembled

The bytes of each stage's parcels in `src/dnfw/waverider/sharc_code.json` (`object_parcels_be`), counted from the
committed file. It is the code before packing, not the room left in the upload: it shows which stage grew.

| release | perc | smp | fascia | smear | mverb | every stage | source |
|---|---|---|---|---|---|---|---|
| v0.27 (3118908) | 9,568 | 23,642 | 145,210 | 6,104 | 4,734 | 190,526 | counted by the review of v0.28, 2026-11-26 |
| v0.28 (frozen 66bffc8) | 9,202 | 23,682 | 142,584 | 6,144 | 3,668 | 186,548 | the same count |

The ColdFire's C chunk (`c_chunk` in `src/dnfw/mods/waverider_code.json`): 216,272 bytes at v0.27, 217,152 at
v0.28; the 192-byte glass chunk is gone.

## Known places to give time back (2026-11-25)

- **CONTOUR**: a step is about 590 cycles (4 or 5 sines, 3 wraps, the surfaces). A table sine,
  or two sines at once on the SHARC's second element set.
- **FASCIA**: coefficients computed every block are about 30 % of a voice, the modes per sample
  about 33 %, the exciters about 16 %.
- **ORGAN, DIGIDRUM**: not yet profiled for this.
- **The master reverb** (2026-11-26, the review of v0.28): 42 line addresses are computed for every sample
  (counted in `mverb.asm`), 38 of them at a delay that does not change within a block. See
  `REVIEW-v0.28.md`, "Optimizations".
