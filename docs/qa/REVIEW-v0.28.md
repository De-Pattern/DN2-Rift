# Review of v0.28

The frozen source `rc/v0.28` at `66bffc8`, against v0.27's source `3118908` (the tip of `rc/v0.27`,
which the tag `v0.27` contains): five commits. Reviewed 2026-11-26 by a fresh session.

**How it was done: by reading.** This session had no bench: the private bench repository, the stock
firmware's sections and the emulators were not there, so no gate step, runner step or unit test was
run (`test_mverb_program.py` stops at import for a bench file). Three things were measured, and are
marked *measured* below: the reverb's tail from its model, the assembled DSP bytes, and the stock
sites RUBBER used to edit. Everything else is *read*.

## 1. Headline

Nothing found that could harm a unit or lose data. No grade A, no grade B. Eight grade C items: the
guard's new floors and the pulled RUBBER came without a gate case that would fail if they were wrong,
and the reverb's tail at DEC 127 is a quarter shorter by measurement, where the manual says a third.

## 2. Findings

**C1. The sample voices' and SMEAR's new floor has no gate case.** *Read.*
`src/dnfw/sampler/program.py:3284` (floor 40,000 on the trigger block, else the last cost x 1.25 and at
least 12,000) and `src/dnfw/smear/stage.py:194-209`. The runner's diff adds profiling (`rprof`
ONESHOT, GRID, SMEAR) and no check, so nothing fails if the floor goes back to 60,000 or down to 0.
v0.27's same change for FASCIA's walk had `fkeep`'s melody (93 voices left out where 244 were).
Proposed step: sixteen ONESHOT tracks and the plate with the clock fed from measured costs, the
voices left out counted; negative control, the floor at 60,000 on every block leaves more out.

**C2. The 40,000 floor rests on two of the seven sample machines.** *Read.*
`src/dnfw/sampler/program.py:1937`: "rprof: ONESHOT, GRID 30,800 at worst". WERP, STRETCH, REPITCH,
SLICE and FLEX have no `rprof` entry in this diff. If one costs more than 40,000 on its trigger
block, that block is under-reserved by the difference; the limit's P/8 absorbs a few such voices, not
sixteen. The case to run: every track on the heaviest sample machine, all triggered on one block.

**C3. SMEAR's cost: the commit and the ledger disagree.** *Read.*
`src/dnfw/smear/stage.py:199` says a SMEAR voice costs 21,000 to 27,000; `docs/qa/LEDGER.md`'s v0.27
row (the build session's run of 2026-11-25) has SMEAR GRN at about 70,000. If 70,000 is right for
dense grains, the trigger block's floor of 40,000 is 30,000 short a track where v0.27's 60,000 was
10,000 short. Worth one `rprof` run of SMEAR GRN at DENS 127, OVLP 127 to settle which, and the
ledger corrected from it.

**C4. RUBBER pulled: the gate's step has no negative control, and one site list is short.** *Read;
the sites measured.* `scripts/sharc_waverider_m5.py`, `step_glass`'s pulled branch returns before the
step's negative control (FREQ + 1/128), so the step as it runs for v0.28 has none.
`test/test_rubber_pulled.py:23` lists the FLTR list, name, LOAD and slot sites but not `GRAPH_SITE`
(0x4006eca0) or `OVER_SITE` (0x400c24b0). Measured here on the frozen `waverider_code.json`: no edit
overlaps any of RUBBER's ten sites, those two included, so the build is right; the test would not
say so if one came back.

**C5. RUBBER's page code is still in the image and still runs.** *Read.*
`csrc/waverider/page.c:204-266` (`glass_active`, `glass_names`, its tables), `:421` (called on every
draw), `:707` and `csrc/sampler/smp_page.c:369` (`rub_knob`). With the LOAD bound stock's, no sound
should hold filter 6, so it idles. But it is the one thing that would act on a filter 6 that reached
a kit some other way: the names and the ABND / DBND knobs would switch to RUBBER's on a track whose
DSP has no filter. See "Not checked", the first item.

**C6. The reverb's tail: a quarter shorter at DEC 127, not a third.** *Measured, from the model.*
`src/dnfw/mverb/live.py:58-63` and `site/rift-manual.html:344` say about a third at DEC 127 (from
ln(1/0.97) / ln(1/0.98) = 1.5, the tank's gain alone). A 50 ms noise burst through `live.Verb`, PRE 0,
FREQ 64, GAIN 64, the seconds to fall 60 dB by the slope of the level:

| DEC | v0.27 (0.88, 0.98) | v0.28 (0.87, 0.97) | new / old |
|---|---|---|---|
| 64 | 4.20 s | 4.05 s | 0.97 |
| 96 | 13.67 s | 12.37 s | 0.90 |
| 127 | 42.1 s | 31.6 s | 0.75 |

DEC 96 ("about a tenth") and below agree with the text. At 127 the tail is still about half a
minute. The script is `docs/qa/v0.28/mverb_tail.py`; the DEC 127 and DEC 96 renders went to the owner.

**C7. The reverb's old loop is kept and never run.** *Read.* `src/dnfw/mverb/program.py:67`,
`FAST = True`, keeps `MG.sample` as the way back. No test or step sets `mverb.program.FAST` to False
(`test_glass_program.py:128` sets GLASS's own `FAST`), so the kept loop can stop matching `live.Verb`
unseen. One parametrised case in `test_mverb_program.py` would hold it.

**C8. DIGIDRUM's names by TYPE are checked at one type of six.** *Read.* `scripts/ship_gate.py`
at line 2900 checks the LFO list's short and long names at TYPE's default (BD MODERN) only. Not
exercised: TYPE turned (the names must follow, `page.c:172`), and going from one DIGIDRUM track to
another of a different type. The code reads right: `dgd_type` decodes as the page itself does
(`smp_page.c:1048`), and controls 4..7 are O1..O4.

Read and found sound, no finding: `rclear` (`smp_page.c:949`: the same word and bit layout as
`invert`, clipped, the mask right at both ends of a word); the scroll's redraw request
(`smp_page.c:1196`: it ends when the word arrives or another screen is drawn); the guard's shortened
`perc_limit` (`perc/guard.py:231`: STRUCK is still cleared first, nothing else reads RESERVE);
`sample_fast`'s address arithmetic against `live.Verb`'s (`mverb/program.py:302-446`); the emitter's
constant tracking across the new raw shifts (`perc/dsl.py:104`); the build with no glass chunk
(`gen_waverider_code.py`, `waverider/coldfire.py:1045`).

## 3. Time and memory

No cycle count was measured (no bench), so the ledger's v0.28 row says so and repeats none of the
build session's figures as its own. Measured from the committed files:

- our DSP code as assembled: 190,526 -> 186,548 bytes (-3,978): fascia -2,626 (the GLASS pass),
  mverb -1,066, perc -366, smp +40, smear +40;
- the ColdFire's C chunk: 216,272 -> 217,152 bytes (+880); the 192-byte glass chunk gone;
- stock edits 92 -> 80, guards 59 -> 39.

## 4. Optimizations

**Done: none.** The charter asks for a cost before and after on the unit's model, and there was no
runner to give one.

**Proposed** (not started; each bit for bit, so no likeness question):

1. **The reverb's line addresses as pointers.** `mverb.asm` computes 42 line addresses a sample
   (counted), 38 of them at a delay fixed within the block (the write and read of each line, the
   fourteen output taps). Each is about six instructions (subtract, mask, base, load the index
   register). A pointer a line advanced once a sample, or the SHARC's circular addressing if index
   registers with their length registers are free there, would leave the four modulated reads as
   they are. Saving: not estimated here beyond the count; to be measured with `rprof MVERB`. About
   two to three hours.
2. **RUBBER's page code out while it is pulled** (C5): `glass_names` on every draw, its tables and
   `rub_knob`, under the same `glass.coldfire.ON`. Gives ColdFire bytes back; size not measured.
   Under an hour.

The ledger's known places (CONTOUR's sines, FASCIA's coefficients a block) stand as they were.

## 5. For the build session

- `test/test_rubber_pulled.py:23`: add `P.GRAPH_SITE` and `P.OVER_SITE` to the sites.
- `scripts/sharc_waverider_m5.py`, `step_glass` pulled: give it a control that fails (for one, the
  run with a GLASS routine's label put back in the text it searches).
- `test/test_mverb_program.py`: one case with `FAST = False`.
- `src/dnfw/mverb/live.py:60` and the manual's v0.28 entry (`scripts/gen_rift_manual.py`): "about a
  quarter" at DEC 127, or the constants' own arithmetic named as the tank's gain only.
- `src/dnfw/smear/stage.py:199` or the ledger's v0.27 row: one of the two SMEAR figures is wrong.
- `csrc/waverider/page.c:204-266, 421, 707`, `csrc/sampler/smp_page.c:369`: RUBBER's C code, dead
  while pulled.
- `scripts/ship_gate.py` at 2900: the DIGIDRUM name check at a second TYPE.
- `rprof`: entries for WERP, STRETCH, REPITCH, SLICE and FLEX, so `SMP_FLOOR` has all seven behind it.

## 6. Not checked

- **A v0.27 project with RUBBER on a track, opened on v0.28.** The gate's step puts filter 6 through
  the stored-sound LOAD and sees Multi-Mode come back. Whether a project's kit reaches RAM through
  that same bound could not be told by reading (it needs the stock disassembly or the emulator). The
  machine types' same mechanism has worked for old projects, which speaks for it. If it did not, the
  track would play with no filter and show RUBBER's names (C5); nothing worse.
- **`rclear` against the stock's SET_PIXEL** (0x40113b90): whether the stock routine does anything
  beyond setting the bit (a changed-area mark) was not read; `invert` has written the canvas the same
  way since before this release.
- The screens: the new long names in the header ("Body Envelope", "Triangle Mod" and the rest) were
  not drawn, so their fit is the gate's text check's word, not this review's.
- Every cycle figure, the bytes to spare in the upload and the image, every runner and emulator
  step, the unit tests.
- The generated files (`*.asm`, `*.json`, the manual's HTML) were not regenerated from their sources.
