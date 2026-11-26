# DSP time and memory, release by release

Kept by the release review (`docs/QA.md`). Cycles a block (32 samples) on the unit's cost model:
instructions + 0.95 x (4 x L2 + 10 x DDR accesses), one voice sounding, less an idle frame
(`scripts/sharc_waverider_m5.py --steps rcost`). The frame is 666,667 cycles; an idle frame is
about 416,000 on the unit. A row is written only from a measurement, with its source.

## One voice, worst block

| release | FASCIA bell (strike) | CONTOUR 1 / 2 / 4 steps | SPALL dense | ORGAN every rank | DIGIDRUM | LIGATURE | SILT | SMEAR GRN | source |
|---|---|---|---|---|---|---|---|---|---|
| v0.27 tree (not released) | 87,800 (112,800) | 25,400 / 44,600 / 82,000 | 27,500 | 26,200 | 27,900 | 39,400 | 15,400 to 35,700 | about 70,000 | the build session's run, 2026-11-25; not re-measured by a review |

A slot with no note, same run: FASCIA 900, ORGAN 860, CONTOUR 1,570, SPALL 1,640, LIGATURE
2,560 instructions.

## Bytes to spare

| release | DSP upload (of 1,048,575 unpacked) | 2 MiB image | source |
|---|---|---|---|
| v0.27 tree (not released) | about 181 before FASCIA's walk shared the guard code, which gave about 2 KB back | reported as about 3.2 KB and as about 800 bytes the same day | the build session's notes, 2026-11-25; to be measured at the first review |

## Known places to give time back (2026-11-25)

- **CONTOUR**: a step is about 590 cycles (4 or 5 sines, 3 wraps, the surfaces). A table sine,
  or two sines at once on the SHARC's second element set.
- **FASCIA**: coefficients computed every block are about 30 % of a voice, the modes per sample
  about 33 %, the exciters about 16 %.
- **ORGAN, DIGIDRUM**: not yet profiled for this.
